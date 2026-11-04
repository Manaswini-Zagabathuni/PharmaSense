"""Synthetic structural fixtures for parser tests; these are not FDA records."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

from pharmasense.ingestion.faers.specification import FAERS_TABLE_SPECS, FaersTable


def blank_record(table: FaersTable, **values: str) -> list[str]:
    """Build an explicitly synthetic row matching the verified column contract."""

    return [values.get(column, "") for column in FAERS_TABLE_SPECS[table].columns]


def write_synthetic_archive(
    path: Path,
    overrides: dict[FaersTable, list[list[str] | bytes]] | None = None,
    header_overrides: dict[FaersTable, tuple[str, ...]] | None = None,
) -> None:
    """Write a minimal complete ZIP whose values have no scientific meaning."""

    synthetic_rows: dict[FaersTable, list[list[str] | bytes]] = {
        FaersTable.DEMO: [
            blank_record(FaersTable.DEMO, PRIMARYID="1", CASEID="1", CASEVERSION="1", I_F_CODE="I")
        ],
        FaersTable.DRUG: [
            blank_record(
                FaersTable.DRUG,
                PRIMARYID="1",
                CASEID="1",
                DRUG_SEQ="1",
                ROLE_COD="PS",
                DRUGNAME="SYNTHETIC_PRODUCT",
            )
        ],
        FaersTable.REAC: [
            blank_record(
                FaersTable.REAC,
                PRIMARYID="1",
                CASEID="1",
                PT="SYNTHETIC_TERM",
            )
        ],
        FaersTable.OUTC: [],
        FaersTable.THER: [],
        FaersTable.INDI: [],
    }
    if overrides:
        synthetic_rows.update(overrides)

    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for table in FaersTable:
            columns = (header_overrides or {}).get(table, FAERS_TABLE_SPECS[table].columns)
            content = bytearray(("$".join(columns).lower() + "\n").encode("ascii"))
            for row in synthetic_rows[table]:
                if isinstance(row, bytes):
                    content.extend(row)
                else:
                    content.extend(("$".join(row) + "\n").encode("ascii"))
            archive.writestr(f"ASCII/{table.value}23Q4.txt", bytes(content))


def write_synthetic_manifest(path: Path, archive: Path, row_counts: dict[FaersTable, int]) -> None:
    """Write a test-only manifest matching a synthetic structural archive."""

    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    manifest = {
        "archive_bytes": archive.stat().st_size,
        "archive_filename": archive.name,
        "archive_sha256": checksum,
        "fda_posted_date": "2024-01-23",
        "landing_page_url": "https://example.invalid/test-only",
        "quarter": 4,
        "resolved_archive_url": "https://example.invalid/synthetic.zip",
        "scoped_rows": {table.value: row_counts.get(table, 0) for table in FaersTable},
        "source": "Synthetic FAERS structural test fixture",
        "year": 2023,
    }
    path.write_text(json.dumps(manifest), encoding="utf-8")
