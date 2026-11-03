"""Safe, read-only access to an FDA quarterly ZIP archive."""

from __future__ import annotations

import hashlib
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from pharmasense.ingestion.faers.specification import FAERS_TABLE_SPECS, FaersTable

_TABLE_MEMBER = re.compile(r"^ASCII/([A-Z]{4})(\d{2})Q([1-4])\.txt$", re.IGNORECASE)


class ArchiveValidationError(ValueError):
    """Raised when an archive violates the expected safe structure."""


@dataclass(frozen=True)
class ArchiveMember:
    """Non-content metadata for one ZIP member."""

    filename: str
    uncompressed_bytes: int
    compressed_bytes: int
    crc32: str


@dataclass(frozen=True)
class ArchiveInspection:
    """Validated archive inventory and resolved table members."""

    members: tuple[ArchiveMember, ...]
    table_members: dict[FaersTable, str]
    year: int
    quarter: int


def sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    """Calculate a file SHA-256 without loading it into memory."""

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_archive(path: Path) -> ArchiveInspection:
    """Validate paths, encryption state, duplicates, and required table members."""

    resolved: dict[FaersTable, str] = {}
    periods: set[tuple[int, int]] = set()
    members: list[ArchiveMember] = []
    normalized_names: set[str] = set()

    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            member_path = PurePosixPath(info.filename)
            if member_path.is_absolute() or ".." in member_path.parts:
                raise ArchiveValidationError(f"unsafe archive path: {info.filename}")
            normalized = info.filename.casefold()
            if normalized in normalized_names:
                raise ArchiveValidationError(f"duplicate archive path: {info.filename}")
            normalized_names.add(normalized)
            if info.flag_bits & 0x1:
                raise ArchiveValidationError(f"encrypted archive member: {info.filename}")

            members.append(
                ArchiveMember(
                    filename=info.filename,
                    uncompressed_bytes=info.file_size,
                    compressed_bytes=info.compress_size,
                    crc32=f"{info.CRC:08x}",
                )
            )
            match = _TABLE_MEMBER.fullmatch(info.filename)
            if match is None:
                continue
            prefix, year_suffix, quarter_text = match.groups()
            table = next(
                (
                    item
                    for item, spec in FAERS_TABLE_SPECS.items()
                    if spec.filename_prefix == prefix.upper()
                ),
                None,
            )
            if table is None:
                continue
            if table in resolved:
                raise ArchiveValidationError(f"multiple members found for {table.value}")
            resolved[table] = info.filename
            periods.add((2000 + int(year_suffix), int(quarter_text)))

    missing = [table for table in FaersTable if table not in resolved]
    if missing:
        names = ", ".join(sorted(table.value for table in missing))
        raise ArchiveValidationError(f"missing required table members: {names}")
    if len(periods) != 1:
        raise ArchiveValidationError(f"table members span unexpected periods: {sorted(periods)}")
    year, quarter = periods.pop()
    return ArchiveInspection(tuple(members), resolved, year, quarter)
