"""Streaming parser for the observed 2023 Q4 FAERS ASCII format."""

from __future__ import annotations

import csv
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum
from io import TextIOWrapper
from pathlib import Path

from pharmasense.ingestion.faers.archive import ArchiveInspection, inspect_archive
from pharmasense.ingestion.faers.specification import (
    FAERS_ASCII_DELIMITER,
    FAERS_TABLE_SPECS,
    FaersTable,
)


class IssueCode(StrEnum):
    """Stable, machine-readable parsing and quality issue codes."""

    HEADER_MISMATCH = "HEADER_MISMATCH"
    ROW_FIELD_COUNT_MISMATCH = "ROW_FIELD_COUNT_MISMATCH"
    MISSING_REQUIRED_VALUE = "MISSING_REQUIRED_VALUE"
    INVALID_IDENTIFIER = "INVALID_IDENTIFIER"
    INVALID_ENCODING = "INVALID_ENCODING"
    INVALID_DATE = "INVALID_DATE"
    UNKNOWN_DRUG_ROLE = "UNKNOWN_DRUG_ROLE"
    DUPLICATE_IDENTIFIER = "DUPLICATE_IDENTIFIER"
    DUPLICATE_RECORD = "DUPLICATE_RECORD"
    ORPHAN_REPORT = "ORPHAN_REPORT"
    CASEID_MISMATCH = "CASEID_MISMATCH"
    ORPHAN_DRUG_SEQUENCE = "ORPHAN_DRUG_SEQUENCE"


class HeaderValidationError(ValueError):
    """Raised before records are emitted when a source header has drifted."""


@dataclass(frozen=True)
class SourceRecord:
    """One structurally accepted record with untouched source values."""

    table: FaersTable
    source_filename: str
    source_row_number: int
    columns: tuple[str, ...]
    values: tuple[str, ...]

    def as_dict(self) -> dict[str, str]:
        """Return a field mapping without altering source values."""

        return dict(zip(self.columns, self.values, strict=True))


@dataclass(frozen=True)
class RejectedRecord:
    """One record that could not be represented under the verified contract."""

    table: FaersTable
    source_filename: str
    source_row_number: int
    values: tuple[str, ...]
    issue_code: IssueCode
    detail: str


ParseEvent = SourceRecord | RejectedRecord


def _contains_surrogate(value: str) -> bool:
    return any("\udc80" <= character <= "\udcff" for character in value)


def iter_table_records(
    archive_path: Path,
    table: FaersTable,
    *,
    inspection: ArchiveInspection | None = None,
) -> tuple[tuple[str, ...], Iterator[ParseEvent]]:
    """Return the verified header and a lazy iterator over one ZIP member.

    The returned iterator owns its ZIP handle and closes it when exhausted or closed.
    """

    verified = inspection or inspect_archive(archive_path)
    source_filename = verified.table_members[table]
    expected_columns = FAERS_TABLE_SPECS[table].columns

    def records() -> Iterator[ParseEvent]:
        with (
            zipfile.ZipFile(archive_path) as archive,
            archive.open(source_filename) as binary,
            TextIOWrapper(binary, encoding="ascii", errors="surrogateescape", newline="") as text,
        ):
            reader = csv.reader(
                text,
                delimiter=FAERS_ASCII_DELIMITER,
                quoting=csv.QUOTE_NONE,
                strict=True,
            )
            actual_header = tuple(column.strip().upper() for column in next(reader, []))
            if actual_header != expected_columns:
                raise HeaderValidationError(
                    f"{IssueCode.HEADER_MISMATCH}: {source_filename}: "
                    f"expected {expected_columns!r}, observed {actual_header!r}"
                )

            required = FAERS_TABLE_SPECS[table].required_columns
            identifier_columns = {"PRIMARYID", "CASEID", "CASEVERSION"}
            sequence_column = FAERS_TABLE_SPECS[table].drug_sequence_column
            if table is FaersTable.DRUG:
                sequence_column = "DRUG_SEQ"
            if sequence_column is not None:
                identifier_columns.add(sequence_column)

            for values_list in reader:
                values = tuple(values_list)
                row_number = reader.line_num
                if len(values) != len(expected_columns):
                    yield RejectedRecord(
                        table,
                        source_filename,
                        row_number,
                        values,
                        IssueCode.ROW_FIELD_COUNT_MISMATCH,
                        f"expected {len(expected_columns)} fields, observed {len(values)}",
                    )
                    continue
                if any(_contains_surrogate(value) for value in values):
                    yield RejectedRecord(
                        table,
                        source_filename,
                        row_number,
                        values,
                        IssueCode.INVALID_ENCODING,
                        "record contains bytes outside verified ASCII encoding",
                    )
                    continue
                record = dict(zip(expected_columns, values, strict=True))
                missing = tuple(column for column in required if record[column] == "")
                if missing:
                    yield RejectedRecord(
                        table,
                        source_filename,
                        row_number,
                        values,
                        IssueCode.MISSING_REQUIRED_VALUE,
                        f"empty required fields: {', '.join(missing)}",
                    )
                    continue
                invalid_ids = tuple(
                    column
                    for column in identifier_columns
                    if record.get(column, "") and not record[column].isdecimal()
                )
                if invalid_ids:
                    yield RejectedRecord(
                        table,
                        source_filename,
                        row_number,
                        values,
                        IssueCode.INVALID_IDENTIFIER,
                        f"non-numeric identifiers: {', '.join(sorted(invalid_ids))}",
                    )
                    continue
                yield SourceRecord(table, source_filename, row_number, expected_columns, values)

    return expected_columns, records()
