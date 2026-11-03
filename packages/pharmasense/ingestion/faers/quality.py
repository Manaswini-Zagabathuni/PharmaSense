"""Bounded-memory data-quality analysis for a FAERS quarterly archive."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import cast

from pharmasense.ingestion.faers.archive import inspect_archive, sha256_file
from pharmasense.ingestion.faers.parser import (
    IssueCode,
    RejectedRecord,
    iter_table_records,
)
from pharmasense.ingestion.faers.specification import (
    FAERS_DATE_COLUMNS,
    FAERS_TABLE_SPECS,
    FaersTable,
)

PARSER_VERSION = "1.0.0"
_BATCH_SIZE = 10_000
_KNOWN_DRUG_ROLES = frozenset({"PS", "SS", "C", "I"})


@dataclass
class TableQuality:
    """Aggregate observations for one source member."""

    source_filename: str
    source_bytes: int
    columns: tuple[str, ...]
    source_records: int = 0
    accepted_records: int = 0
    rejected_records: int = 0
    missing_values: dict[str, int] = field(default_factory=dict)
    invalid_values: dict[str, int] = field(default_factory=dict)
    issue_counts: dict[str, int] = field(default_factory=dict)
    duplicate_identifier_records: int = 0
    duplicate_exact_records: int = 0
    invalid_relationships: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class QualityReport:
    """Deterministic machine-readable quality report."""

    report_id: str
    parser_version: str
    archive_filename: str
    archive_bytes: int
    archive_sha256: str
    source_year: int
    source_quarter: int
    members: tuple[dict[str, str | int], ...]
    tables: dict[str, TableQuality]
    total_source_records: int
    total_accepted_records: int
    total_rejected_records: int

    def to_dict(self) -> dict[str, object]:
        """Convert to JSON-compatible primitives in deterministic order."""

        return cast(dict[str, object], asdict(self))


def _valid_partial_date(value: str) -> bool:
    if not value.isdecimal() or len(value) not in {4, 6, 8}:
        return False
    year = int(value[:4])
    if len(value) == 4:
        return 1000 <= year <= 2999
    month = int(value[4:6])
    if len(value) == 6:
        return 1000 <= year <= 2999 and 1 <= month <= 12
    try:
        date(year, month, int(value[6:8]))
    except ValueError:
        return False
    return True


def _identity_key(table: FaersTable, record: dict[str, str], values: tuple[str, ...]) -> str:
    if table is FaersTable.DEMO:
        return record["PRIMARYID"]
    if table is FaersTable.DRUG:
        return f"{record['PRIMARYID']}\x1f{record['DRUG_SEQ']}"
    return hashlib.sha256(
        json.dumps(values, ensure_ascii=True, separators=(",", ":")).encode("ascii")
    ).hexdigest()


def _excess_duplicates(connection: sqlite3.Connection, table: FaersTable, column: str) -> int:
    result = connection.execute(
        f"""SELECT COALESCE(SUM(item_count - 1), 0)
            FROM (
                SELECT COUNT(*) AS item_count
                FROM records
                WHERE table_name = ?
                GROUP BY {column}
                HAVING COUNT(*) > 1
            )""",  # noqa: S608 -- column is an internal constant, values remain parameterized.
        (table.value,),
    ).fetchone()
    return int(result[0])


def _relationship_counts(connection: sqlite3.Connection, table: FaersTable) -> dict[str, int]:
    counts: dict[str, int] = {}
    orphan_report = connection.execute(
        """SELECT COUNT(*) FROM records AS child
           WHERE child.table_name = ?
             AND NOT EXISTS (
               SELECT 1 FROM records AS parent
               WHERE parent.table_name = 'DEMO'
                 AND parent.primaryid = child.primaryid
             )""",
        (table.value,),
    ).fetchone()
    counts[IssueCode.ORPHAN_REPORT.value] = int(orphan_report[0])
    case_mismatch = connection.execute(
        """SELECT COUNT(*) FROM records AS child
           WHERE child.table_name = ?
             AND EXISTS (
               SELECT 1 FROM records AS parent
               WHERE parent.table_name = 'DEMO'
                 AND parent.primaryid = child.primaryid
                 AND parent.caseid <> child.caseid
             )""",
        (table.value,),
    ).fetchone()
    counts[IssueCode.CASEID_MISMATCH.value] = int(case_mismatch[0])
    if table in {FaersTable.THER, FaersTable.INDI}:
        orphan_drug = connection.execute(
            """SELECT COUNT(*) FROM records AS child
               WHERE child.table_name = ?
                 AND NOT EXISTS (
                   SELECT 1 FROM records AS drug
                   WHERE drug.table_name = 'DRUG'
                     AND drug.primaryid = child.primaryid
                     AND drug.drug_seq = child.drug_seq
                 )""",
            (table.value,),
        ).fetchone()
        counts[IssueCode.ORPHAN_DRUG_SEQUENCE.value] = int(orphan_drug[0])
    return counts


def analyze_archive(archive_path: Path) -> QualityReport:
    """Stream all scoped tables and return reproducible aggregate quality observations."""

    inspection = inspect_archive(archive_path)
    archive_sha256 = sha256_file(archive_path)
    report_id = hashlib.sha256(f"{archive_sha256}:{PARSER_VERSION}".encode()).hexdigest()
    member_sizes = {member.filename: member.uncompressed_bytes for member in inspection.members}
    table_reports: dict[str, TableQuality] = {}

    with tempfile.TemporaryDirectory(prefix="pharmasense-faers-") as temp_dir:
        database_path = Path(temp_dir) / "quality-index.sqlite3"
        connection = sqlite3.connect(database_path)
        try:
            connection.execute("PRAGMA journal_mode = OFF")
            connection.execute("PRAGMA synchronous = OFF")
            connection.execute(
                """CREATE TABLE records (
                    table_name TEXT NOT NULL,
                    row_number INTEGER NOT NULL,
                    primaryid TEXT NOT NULL,
                    caseid TEXT NOT NULL,
                    drug_seq TEXT,
                    identity_key TEXT NOT NULL,
                    record_hash TEXT NOT NULL
                )"""
            )

            for table in FaersTable:
                source_filename = inspection.table_members[table]
                columns, events = iter_table_records(archive_path, table, inspection=inspection)
                quality = TableQuality(
                    source_filename=source_filename,
                    source_bytes=member_sizes[source_filename],
                    columns=columns,
                    missing_values={column: 0 for column in columns},
                )
                issue_counts: Counter[str] = Counter()
                invalid_counts: Counter[str] = Counter()
                batch: list[tuple[str, int, str, str, str | None, str, str]] = []

                for event in events:
                    quality.source_records += 1
                    if isinstance(event, RejectedRecord):
                        quality.rejected_records += 1
                        issue_counts[event.issue_code.value] += 1
                        if len(event.values) == len(columns):
                            for column, value in zip(columns, event.values, strict=True):
                                if value == "":
                                    quality.missing_values[column] += 1
                        continue

                    quality.accepted_records += 1
                    record = event.as_dict()
                    for column, value in record.items():
                        if value == "":
                            quality.missing_values[column] += 1
                    for column in FAERS_DATE_COLUMNS[table]:
                        value = record[column]
                        if value and not _valid_partial_date(value):
                            invalid_counts[column] += 1
                            issue_counts[IssueCode.INVALID_DATE.value] += 1
                    if table is FaersTable.DRUG and record["ROLE_COD"] not in _KNOWN_DRUG_ROLES:
                        invalid_counts["ROLE_COD"] += 1
                        issue_counts[IssueCode.UNKNOWN_DRUG_ROLE.value] += 1

                    sequence_column = FAERS_TABLE_SPECS[table].drug_sequence_column
                    if table is FaersTable.DRUG:
                        sequence_column = "DRUG_SEQ"
                    drug_sequence = record[sequence_column] if sequence_column else None
                    record_hash = hashlib.sha256(
                        "\x1f".join(event.values).encode("ascii")
                    ).hexdigest()
                    batch.append(
                        (
                            table.value,
                            event.source_row_number,
                            record["PRIMARYID"],
                            record["CASEID"],
                            drug_sequence,
                            _identity_key(table, record, event.values),
                            record_hash,
                        )
                    )
                    if len(batch) >= _BATCH_SIZE:
                        connection.executemany(
                            "INSERT INTO records VALUES (?, ?, ?, ?, ?, ?, ?)", batch
                        )
                        batch.clear()
                if batch:
                    connection.executemany(
                        "INSERT INTO records VALUES (?, ?, ?, ?, ?, ?, ?)", batch
                    )
                connection.commit()
                quality.invalid_values = dict(sorted(invalid_counts.items()))
                quality.issue_counts = dict(sorted(issue_counts.items()))
                table_reports[table.value] = quality

            connection.execute(
                "CREATE INDEX records_report_idx ON records (table_name, primaryid, caseid)"
            )
            connection.execute(
                "CREATE INDEX records_drug_idx ON records (table_name, primaryid, drug_seq)"
            )
            connection.execute(
                "CREATE INDEX records_identity_idx ON records (table_name, identity_key)"
            )
            connection.execute("CREATE INDEX records_hash_idx ON records (table_name, record_hash)")

            for table in FaersTable:
                quality = table_reports[table.value]
                if table in {FaersTable.DEMO, FaersTable.DRUG}:
                    quality.duplicate_identifier_records = _excess_duplicates(
                        connection, table, "identity_key"
                    )
                quality.duplicate_exact_records = _excess_duplicates(
                    connection, table, "record_hash"
                )
                if quality.duplicate_identifier_records:
                    quality.issue_counts[IssueCode.DUPLICATE_IDENTIFIER.value] = (
                        quality.duplicate_identifier_records
                    )
                if quality.duplicate_exact_records:
                    quality.issue_counts[IssueCode.DUPLICATE_RECORD.value] = (
                        quality.duplicate_exact_records
                    )
                if table is not FaersTable.DEMO:
                    quality.invalid_relationships = _relationship_counts(connection, table)
                    for code, count in quality.invalid_relationships.items():
                        if count:
                            quality.issue_counts[code] = count
                quality.issue_counts = dict(sorted(quality.issue_counts.items()))
        finally:
            connection.close()

    total_source = sum(item.source_records for item in table_reports.values())
    total_accepted = sum(item.accepted_records for item in table_reports.values())
    total_rejected = sum(item.rejected_records for item in table_reports.values())
    member_rows: list[dict[str, str | int]] = []
    for member in inspection.members:
        member_rows.append(
            {
                "filename": member.filename,
                "uncompressed_bytes": member.uncompressed_bytes,
                "compressed_bytes": member.compressed_bytes,
                "crc32": member.crc32,
            }
        )
    return QualityReport(
        report_id=report_id,
        parser_version=PARSER_VERSION,
        archive_filename=archive_path.name,
        archive_bytes=archive_path.stat().st_size,
        archive_sha256=archive_sha256,
        source_year=inspection.year,
        source_quarter=inspection.quarter,
        members=tuple(member_rows),
        tables=table_reports,
        total_source_records=total_source,
        total_accepted_records=total_accepted,
        total_rejected_records=total_rejected,
    )
