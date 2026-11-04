"""Restartable, dependency-aware persistence for verified FAERS ASCII archives."""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, cast

from sqlalchemy import Connection, Engine, func, insert, inspect, select, text, update
from sqlalchemy.exc import SQLAlchemyError

from pharmasense.db.models import (
    FaersCase,
    FaersDrug,
    FaersDrugSequence,
    FaersIndication,
    FaersOutcome,
    FaersReaction,
    FaersReportVersion,
    FaersTherapy,
    IngestionIssue,
    IngestionRun,
    SourceArtifact,
    SourceMember,
)
from pharmasense.db.models import (
    RejectedRecord as DatabaseRejectedRecord,
)
from pharmasense.ingestion.faers.archive import ArchiveInspection, inspect_archive, sha256_file
from pharmasense.ingestion.faers.parser import (
    IssueCode,
    ParseEvent,
    RejectedRecord,
    SourceRecord,
    iter_table_records,
)
from pharmasense.ingestion.faers.quality import PARSER_VERSION
from pharmasense.ingestion.faers.specification import FAERS_TABLE_SPECS, FaersTable

SCHEMA_VERSION = "20261103_0002"
DEFAULT_BATCH_SIZE = 5_000
LOAD_ORDER = (
    FaersTable.DEMO,
    FaersTable.DRUG,
    FaersTable.REAC,
    FaersTable.OUTC,
    FaersTable.THER,
    FaersTable.INDI,
)


class IngestionStatus(StrEnum):
    """Persisted lifecycle states for an ingestion run."""

    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"


class IngestionValidationError(ValueError):
    """Raised when source identity or reconciliation does not match its manifest."""


@dataclass(frozen=True)
class SourceManifest:
    """Minimum immutable source contract read from the committed manifest."""

    archive_filename: str
    archive_bytes: int
    archive_sha256: str
    source_name: str
    source_url: str
    landing_page_url: str | None
    posted_date: date | None
    year: int
    quarter: int
    scoped_rows: dict[str, int]


@dataclass
class TableProgress:
    """Checkpointed counters for one source member."""

    last_source_row: int = 1
    source_rows: int = 0
    accepted_rows: int = 0
    rejected_rows: int = 0
    inserted_rows: int = 0
    skipped_rows: int = 0
    batches: int = 0
    complete: bool = False


@dataclass(frozen=True)
class TableReconciliation:
    """Final or partial reconciliation for one source table."""

    source_rows: int
    expected_source_rows: int
    accepted_rows: int
    rejected_rows: int
    inserted_rows: int
    skipped_rows: int
    previously_existing_rows: int
    batches: int
    complete: bool


@dataclass(frozen=True)
class IngestionReconciliation:
    """Machine-readable outcome for one ingestion invocation."""

    run_id: int
    status: str
    no_op: bool
    source_year: int
    source_quarter: int
    archive_filename: str
    archive_sha256: str
    parser_version: str
    schema_version: str
    batch_size: int
    resume_count: int
    duration_seconds: float
    tables: dict[str, TableReconciliation]
    database_rows_for_artifact: dict[str, int]
    database_rows_total: dict[str, int]
    foreign_key_violations: dict[str, int]
    duplicate_handling: dict[str, int]
    missing_parent_references: dict[str, int]

    def to_dict(self) -> dict[str, object]:
        """Return deterministic JSON-compatible values."""

        return cast(dict[str, object], asdict(self))


def load_source_manifest(path: Path) -> SourceManifest:
    """Load the committed source manifest without accepting implicit source selection."""

    raw = cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))
    posted = raw.get("fda_posted_date")
    return SourceManifest(
        archive_filename=str(raw["archive_filename"]),
        archive_bytes=int(cast(int, raw["archive_bytes"])),
        archive_sha256=str(raw["archive_sha256"]),
        source_name=str(raw["source"]),
        source_url=str(raw["resolved_archive_url"]),
        landing_page_url=(
            str(raw["landing_page_url"]) if raw.get("landing_page_url") is not None else None
        ),
        posted_date=date.fromisoformat(str(posted)) if posted is not None else None,
        year=int(cast(int, raw["year"])),
        quarter=int(cast(int, raw["quarter"])),
        scoped_rows={
            str(key): int(value) for key, value in cast(dict[str, int], raw["scoped_rows"]).items()
        },
    )


def validate_source(
    archive_path: Path,
    manifest: SourceManifest,
    *,
    year: int,
    quarter: int,
) -> tuple[ArchiveInspection, str]:
    """Verify period, filename, byte length, and SHA-256 before database mutation."""

    if (manifest.year, manifest.quarter) != (year, quarter):
        raise IngestionValidationError(
            f"manifest period is {manifest.year}Q{manifest.quarter}, requested {year}Q{quarter}"
        )
    if archive_path.name != manifest.archive_filename:
        raise IngestionValidationError(
            "archive filename mismatch: "
            f"expected {manifest.archive_filename}, got {archive_path.name}"
        )
    if archive_path.stat().st_size != manifest.archive_bytes:
        raise IngestionValidationError("archive byte size does not match the committed manifest")
    inspection = inspect_archive(archive_path)
    if (inspection.year, inspection.quarter) != (year, quarter):
        raise IngestionValidationError(
            f"archive members identify {inspection.year}Q{inspection.quarter}, "
            f"requested {year}Q{quarter}"
        )
    checksum = sha256_file(archive_path)
    if checksum != manifest.archive_sha256:
        raise IngestionValidationError("archive SHA-256 does not match the committed manifest")
    return inspection, checksum


def _idempotency_key(checksum: str, year: int, quarter: int) -> str:
    identity = f"{checksum}:{PARSER_VERSION}:{SCHEMA_VERSION}:{year}Q{quarter}"
    return hashlib.sha256(identity.encode("ascii")).hexdigest()


def _default_configuration(batch_size: int, year: int, quarter: int) -> dict[str, object]:
    return {
        "batch_size": batch_size,
        "source_year": year,
        "source_quarter": quarter,
        "resume_count": 0,
        "tables": {table.value: asdict(TableProgress()) for table in LOAD_ORDER},
    }


def _as_int(value: object) -> int:
    """Convert a JSON-compatible checkpoint number under strict typing."""

    if not isinstance(value, int | str):
        raise IngestionValidationError(f"invalid numeric checkpoint value: {value!r}")
    return int(value)


def _table_progress(configuration: Mapping[str, object], table: FaersTable) -> TableProgress:
    tables = cast(dict[str, dict[str, object]], configuration["tables"])
    raw = tables[table.value]
    return TableProgress(
        last_source_row=_as_int(raw.get("last_source_row", 1)),
        source_rows=_as_int(raw.get("source_rows", 0)),
        accepted_rows=_as_int(raw.get("accepted_rows", 0)),
        rejected_rows=_as_int(raw.get("rejected_rows", 0)),
        inserted_rows=_as_int(raw.get("inserted_rows", 0)),
        skipped_rows=_as_int(raw.get("skipped_rows", 0)),
        batches=_as_int(raw.get("batches", 0)),
        complete=bool(raw.get("complete", False)),
    )


def _save_progress(
    configuration: dict[str, object], table: FaersTable, progress: TableProgress
) -> None:
    tables = cast(dict[str, dict[str, object]], configuration["tables"])
    tables[table.value] = asdict(progress)


def _chunks(events: Iterable[ParseEvent], size: int) -> Iterator[list[ParseEvent]]:
    batch: list[ParseEvent] = []
    for event in events:
        batch.append(event)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch


def _verify_schema(engine: Engine, *, require_migration: bool) -> None:
    expected = {
        "source_artifact",
        "source_member",
        "ingestion_run",
        "faers_case",
        "faers_report_version",
        "faers_drug_sequence",
        "faers_drug",
        "faers_reaction",
        "faers_outcome",
        "faers_therapy",
        "faers_indication",
        "ingestion_issue",
        "rejected_record",
    }
    observed = set(inspect(engine).get_table_names())
    missing = expected - observed
    if missing:
        raise IngestionValidationError(f"database schema is missing tables: {sorted(missing)}")
    if require_migration:
        if "alembic_version" not in observed:
            raise IngestionValidationError("database has no Alembic version table")
        with engine.connect() as connection:
            revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
        if revision != SCHEMA_VERSION:
            raise IngestionValidationError(
                f"database revision is {revision!r}; expected {SCHEMA_VERSION}"
            )


def _register_provenance(
    connection: Connection,
    archive_path: Path,
    manifest: SourceManifest,
    inspection: ArchiveInspection,
    checksum: str,
    batch_size: int,
) -> tuple[int, dict[FaersTable, int], int, dict[str, object], bool]:
    artifact_id = connection.scalar(
        select(SourceArtifact.id).where(SourceArtifact.sha256 == checksum)
    )
    if artifact_id is None:
        result = connection.execute(
            insert(SourceArtifact).values(
                source_name=manifest.source_name,
                source_system="FAERS",
                source_year=manifest.year,
                source_quarter=manifest.quarter,
                archive_format="ASCII_ZIP",
                source_url=manifest.source_url,
                landing_page_url=manifest.landing_page_url,
                posted_date=manifest.posted_date,
                retrieved_at=datetime.fromtimestamp(archive_path.stat().st_mtime, tz=UTC),
                filename=manifest.archive_filename,
                storage_path=str(archive_path),
                byte_size=manifest.archive_bytes,
                sha256=checksum,
            )
        )
        artifact_id = cast(int, result.inserted_primary_key[0])

    member_metadata = {member.filename: member for member in inspection.members}
    member_ids: dict[FaersTable, int] = {}
    for table in LOAD_ORDER:
        member_path = inspection.table_members[table]
        member_id = connection.scalar(
            select(SourceMember.id).where(
                SourceMember.artifact_id == artifact_id,
                SourceMember.member_path == member_path,
            )
        )
        if member_id is None:
            metadata = member_metadata[member_path]
            result = connection.execute(
                insert(SourceMember).values(
                    artifact_id=artifact_id,
                    logical_table=table.value,
                    member_path=member_path,
                    uncompressed_bytes=metadata.uncompressed_bytes,
                    compressed_bytes=metadata.compressed_bytes,
                    crc32=metadata.crc32,
                    header=list(FAERS_TABLE_SPECS[table].columns),
                    row_count=manifest.scoped_rows[table.value],
                )
            )
            member_id = cast(int, result.inserted_primary_key[0])
        member_ids[table] = member_id

    key = _idempotency_key(checksum, manifest.year, manifest.quarter)
    run_row = (
        connection.execute(
            select(
                IngestionRun.id,
                IngestionRun.status,
                IngestionRun.configuration,
            ).where(IngestionRun.idempotency_key == key)
        )
        .mappings()
        .one_or_none()
    )
    already_complete = run_row is not None and run_row["status"] == IngestionStatus.COMPLETED.value
    if run_row is None:
        configuration = _default_configuration(batch_size, manifest.year, manifest.quarter)
        result = connection.execute(
            insert(IngestionRun).values(
                artifact_id=artifact_id,
                idempotency_key=key,
                parser_version=PARSER_VERSION,
                schema_version=SCHEMA_VERSION,
                status=IngestionStatus.RUNNING.value,
                configuration=configuration,
                started_at=datetime.now(UTC),
                accepted_records=0,
                rejected_records=0,
                warning_count=0,
                report_id=key,
            )
        )
        run_id = cast(int, result.inserted_primary_key[0])
    else:
        run_id = _as_int(run_row["id"])
        configuration = cast(dict[str, object], run_row["configuration"])
        if not already_complete:
            configuration = json.loads(json.dumps(configuration))
            configuration["resume_count"] = _as_int(configuration.get("resume_count", 0)) + 1
            configuration["batch_size"] = batch_size
            connection.execute(
                update(IngestionRun)
                .where(IngestionRun.id == run_id)
                .values(
                    status=IngestionStatus.RUNNING.value,
                    finished_at=None,
                    configuration=configuration,
                )
            )
    return artifact_id, member_ids, run_id, configuration, already_complete


def _existing_values(connection: Connection, column: Any, values: Iterable[str]) -> set[str]:
    unique_values = set(values)
    if not unique_values:
        return set()
    return set(connection.scalars(select(column).where(column.in_(unique_values))))


def _existing_source_rows(
    connection: Connection, model: Any, member_id: int, rows: Iterable[int]
) -> set[int]:
    row_numbers = set(rows)
    if not row_numbers:
        return set()
    return set(
        connection.scalars(
            select(model.source_row_number).where(
                model.source_member_id == member_id,
                model.source_row_number.in_(row_numbers),
            )
        )
    )


def _rejection_values(
    event: ParseEvent,
    *,
    run_id: int,
    member_id: int,
    issue_code: IssueCode,
    detail: str,
) -> tuple[dict[str, object], dict[str, object]]:
    payload = "$".join(event.values)
    digest = hashlib.sha256(payload.encode("ascii", errors="backslashreplace")).hexdigest()
    rejected: dict[str, object] = {
        "ingestion_run_id": run_id,
        "source_member_id": member_id,
        "source_row_number": event.source_row_number,
        "logical_table": event.table.value,
        "raw_record_sha256": digest,
        "raw_payload": payload,
        "issue_codes": [issue_code.value],
    }
    issue: dict[str, object] = {
        "ingestion_run_id": run_id,
        "source_member_id": member_id,
        "source_row_number": event.source_row_number,
        "logical_table": event.table.value,
        "severity": "ERROR",
        "issue_code": issue_code.value,
        "value_sha256": digest,
        "details": {"detail": detail},
        "occurrence_count": 1,
    }
    return rejected, issue


def _source_values(record: SourceRecord) -> dict[str, str]:
    return record.as_dict()


_DEMO_FIELDS = (
    "I_F_CODE",
    "EVENT_DT",
    "MFR_DT",
    "INIT_FDA_DT",
    "FDA_DT",
    "REPT_COD",
    "AUTH_NUM",
    "MFR_NUM",
    "MFR_SNDR",
    "LIT_REF",
    "AGE",
    "AGE_COD",
    "AGE_GRP",
    "SEX",
    "E_SUB",
    "WT",
    "WT_COD",
    "REPT_DT",
    "TO_MFR",
    "OCCP_COD",
    "REPORTER_COUNTRY",
    "OCCR_COUNTRY",
)

_DRUG_FIELDS = (
    "ROLE_COD",
    "DRUGNAME",
    "PROD_AI",
    "VAL_VBM",
    "ROUTE",
    "DOSE_VBM",
    "CUM_DOSE_CHR",
    "CUM_DOSE_UNIT",
    "DECHAL",
    "RECHAL",
    "LOT_NUM",
    "EXP_DT",
    "NDA_NUM",
    "DOSE_AMT",
    "DOSE_UNIT",
    "DOSE_FORM",
    "DOSE_FREQ",
)


def _lower_source_fields(source: Mapping[str, str], fields: Iterable[str]) -> dict[str, str]:
    return {field.lower(): source[field] for field in fields}


def _persist_demo(
    connection: Connection,
    records: list[SourceRecord],
    *,
    run_id: int,
    member_id: int,
    year: int,
    quarter: int,
) -> tuple[int, int, list[tuple[SourceRecord, IssueCode, str]]]:
    existing_rows = _existing_source_rows(
        connection, FaersReportVersion, member_id, (item.source_row_number for item in records)
    )
    pending = [item for item in records if item.source_row_number not in existing_rows]
    sources = [(item, _source_values(item)) for item in pending]
    primary_ids = {source["PRIMARYID"] for _, source in sources}
    existing_reports = {
        str(row["primary_id"]): row
        for row in connection.execute(
            select(FaersReportVersion.__table__).where(
                FaersReportVersion.primary_id.in_(primary_ids)
            )
        ).mappings()
    }
    to_insert: list[tuple[SourceRecord, dict[str, str]]] = []
    conflicts: list[tuple[SourceRecord, IssueCode, str]] = []
    skipped_reports = 0
    for item, source in sources:
        existing = existing_reports.get(source["PRIMARYID"])
        if existing is None:
            to_insert.append((item, source))
            continue
        expected = {
            "case_id": source["CASEID"],
            "case_version": source["CASEVERSION"],
            **_lower_source_fields(source, _DEMO_FIELDS),
        }
        if any(existing[column] != value for column, value in expected.items()):
            conflicts.append(
                (
                    item,
                    IssueCode.DUPLICATE_IDENTIFIER,
                    "PRIMARYID already exists with conflicting source values",
                )
            )
        else:
            skipped_reports += 1
    existing_cases = _existing_values(
        connection, FaersCase.case_id, (source["CASEID"] for _, source in to_insert)
    )
    new_cases = sorted({source["CASEID"] for _, source in to_insert} - existing_cases)
    if new_cases:
        connection.execute(
            insert(FaersCase),
            [{"case_id": case_id, "created_by_run_id": run_id} for case_id in new_cases],
        )
    if to_insert:
        connection.execute(
            insert(FaersReportVersion),
            [
                {
                    "primary_id": source["PRIMARYID"],
                    "case_id": source["CASEID"],
                    "case_version": source["CASEVERSION"],
                    "source_year": year,
                    "source_quarter": quarter,
                    "source_member_id": member_id,
                    "ingestion_run_id": run_id,
                    "source_row_number": item.source_row_number,
                    **_lower_source_fields(source, _DEMO_FIELDS),
                }
                for item, source in to_insert
            ],
        )
    skipped = len(existing_rows) + skipped_reports
    return len(to_insert), skipped, conflicts


def _partition_by_report(
    connection: Connection, records: list[SourceRecord]
) -> tuple[list[tuple[SourceRecord, dict[str, str]]], list[tuple[SourceRecord, IssueCode, str]]]:
    sources = [(item, _source_values(item)) for item in records]
    existing = _existing_values(
        connection, FaersReportVersion.primary_id, (source["PRIMARYID"] for _, source in sources)
    )
    accepted: list[tuple[SourceRecord, dict[str, str]]] = []
    rejected: list[tuple[SourceRecord, IssueCode, str]] = []
    for item, source in sources:
        if source["PRIMARYID"] in existing:
            accepted.append((item, source))
        else:
            rejected.append((item, IssueCode.ORPHAN_REPORT, "report version is not present"))
    return accepted, rejected


def _persist_drug(
    connection: Connection,
    records: list[SourceRecord],
    *,
    run_id: int,
    member_id: int,
    year: int,
    quarter: int,
) -> tuple[int, int, list[tuple[SourceRecord, IssueCode, str]]]:
    existing_rows = _existing_source_rows(
        connection, FaersDrug, member_id, (item.source_row_number for item in records)
    )
    pending = [item for item in records if item.source_row_number not in existing_rows]
    accepted, rejected = _partition_by_report(connection, pending)
    sequence_keys = {(source["PRIMARYID"], source["DRUG_SEQ"]) for _, source in accepted}
    existing_sequences = (
        set(
            connection.execute(
                select(FaersDrugSequence.primary_id, FaersDrugSequence.drug_seq).where(
                    FaersDrugSequence.primary_id.in_({key[0] for key in sequence_keys})
                )
            ).tuples()
        )
        if sequence_keys
        else set()
    )
    new_sequences = sorted(sequence_keys - existing_sequences)
    if new_sequences:
        connection.execute(
            insert(FaersDrugSequence),
            [
                {
                    "primary_id": primary_id,
                    "drug_seq": drug_seq,
                    "source_member_id": member_id,
                    "ingestion_run_id": run_id,
                    "source_year": year,
                    "source_quarter": quarter,
                }
                for primary_id, drug_seq in new_sequences
            ],
        )
    if accepted:
        connection.execute(
            insert(FaersDrug),
            [
                {
                    "primary_id": source["PRIMARYID"],
                    "source_case_id": source["CASEID"],
                    "drug_seq": source["DRUG_SEQ"],
                    "source_member_id": member_id,
                    "ingestion_run_id": run_id,
                    "source_row_number": item.source_row_number,
                    **_lower_source_fields(source, _DRUG_FIELDS),
                }
                for item, source in accepted
            ],
        )
    return len(accepted), len(existing_rows), rejected


def _partition_by_sequence(
    connection: Connection,
    records: list[SourceRecord],
    sequence_column: str,
) -> tuple[list[tuple[SourceRecord, dict[str, str]]], list[tuple[SourceRecord, IssueCode, str]]]:
    sources = [(item, _source_values(item)) for item in records]
    primary_ids = {source["PRIMARYID"] for _, source in sources}
    existing = (
        set(
            connection.execute(
                select(FaersDrugSequence.primary_id, FaersDrugSequence.drug_seq).where(
                    FaersDrugSequence.primary_id.in_(primary_ids)
                )
            ).tuples()
        )
        if primary_ids
        else set()
    )
    accepted: list[tuple[SourceRecord, dict[str, str]]] = []
    rejected: list[tuple[SourceRecord, IssueCode, str]] = []
    for item, source in sources:
        if (source["PRIMARYID"], source[sequence_column]) in existing:
            accepted.append((item, source))
        else:
            rejected.append((item, IssueCode.ORPHAN_DRUG_SEQUENCE, "drug sequence is not present"))
    return accepted, rejected


def _persist_simple_child(
    connection: Connection,
    records: list[SourceRecord],
    *,
    table: FaersTable,
    run_id: int,
    member_id: int,
) -> tuple[int, int, list[tuple[SourceRecord, IssueCode, str]]]:
    models = {
        FaersTable.REAC: FaersReaction,
        FaersTable.OUTC: FaersOutcome,
        FaersTable.THER: FaersTherapy,
        FaersTable.INDI: FaersIndication,
    }
    model = models[table]
    existing_rows = _existing_source_rows(
        connection, model, member_id, (item.source_row_number for item in records)
    )
    pending = [item for item in records if item.source_row_number not in existing_rows]
    if table in {FaersTable.THER, FaersTable.INDI}:
        sequence_column = "DSG_DRUG_SEQ" if table is FaersTable.THER else "INDI_DRUG_SEQ"
        accepted, rejected = _partition_by_sequence(connection, pending, sequence_column)
    else:
        accepted, rejected = _partition_by_report(connection, pending)

    mappings: list[dict[str, object]] = []
    for item, source in accepted:
        common: dict[str, object] = {
            "primary_id": source["PRIMARYID"],
            "source_case_id": source["CASEID"],
            "source_member_id": member_id,
            "ingestion_run_id": run_id,
            "source_row_number": item.source_row_number,
        }
        if table is FaersTable.REAC:
            common.update(pt=source["PT"], drug_rec_act=source["DRUG_REC_ACT"])
        elif table is FaersTable.OUTC:
            common.update(outc_cod=source["OUTC_COD"])
        elif table is FaersTable.THER:
            common.update(
                drug_seq=source["DSG_DRUG_SEQ"],
                start_dt=source["START_DT"],
                end_dt=source["END_DT"],
                dur=source["DUR"],
                dur_cod=source["DUR_COD"],
            )
        else:
            common.update(drug_seq=source["INDI_DRUG_SEQ"], indi_pt=source["INDI_PT"])
        mappings.append(common)
    if mappings:
        connection.execute(insert(model), mappings)
    return len(mappings), len(existing_rows), rejected


def _persist_batch(
    connection: Connection,
    events: list[ParseEvent],
    *,
    table: FaersTable,
    run_id: int,
    member_id: int,
    year: int,
    quarter: int,
) -> tuple[int, int, int, list[tuple[ParseEvent, IssueCode, str]]]:
    parser_rejections = [event for event in events if isinstance(event, RejectedRecord)]
    records = [event for event in events if isinstance(event, SourceRecord)]
    if table is FaersTable.DEMO:
        inserted, skipped, relationship_rejections = _persist_demo(
            connection,
            records,
            run_id=run_id,
            member_id=member_id,
            year=year,
            quarter=quarter,
        )
    elif table is FaersTable.DRUG:
        inserted, skipped, relationship_rejections = _persist_drug(
            connection,
            records,
            run_id=run_id,
            member_id=member_id,
            year=year,
            quarter=quarter,
        )
    else:
        inserted, skipped, relationship_rejections = _persist_simple_child(
            connection,
            records,
            table=table,
            run_id=run_id,
            member_id=member_id,
        )
    if any(code is IssueCode.DUPLICATE_IDENTIFIER for _, code, _ in relationship_rejections):
        raise IngestionValidationError(
            "existing PRIMARYID conflicts with immutable report-version source values"
        )
    rejected: list[tuple[ParseEvent, IssueCode, str]] = [
        (event, event.issue_code, event.detail) for event in parser_rejections
    ]
    rejected.extend(relationship_rejections)
    if rejected:
        rejected_rows: list[dict[str, object]] = []
        issue_rows: list[dict[str, object]] = []
        for event, code, detail in rejected:
            rejected_row, issue_row = _rejection_values(
                event,
                run_id=run_id,
                member_id=member_id,
                issue_code=code,
                detail=detail,
            )
            rejected_rows.append(rejected_row)
            issue_rows.append(issue_row)
        connection.execute(insert(DatabaseRejectedRecord), rejected_rows)
        connection.execute(insert(IngestionIssue), issue_rows)
    accepted = inserted + skipped
    return accepted, len(rejected), inserted, rejected


def _progress_totals(configuration: Mapping[str, object]) -> tuple[int, int, int]:
    items = [_table_progress(configuration, table) for table in LOAD_ORDER]
    accepted = sum(item.accepted_rows for item in items)
    rejected = sum(item.rejected_rows for item in items)
    return accepted, rejected, rejected


_DATABASE_MODELS: dict[str, Any] = {
    "faers_case": FaersCase,
    "faers_report_version": FaersReportVersion,
    "faers_drug_sequence": FaersDrugSequence,
    "faers_drug": FaersDrug,
    "faers_reaction": FaersReaction,
    "faers_outcome": FaersOutcome,
    "faers_therapy": FaersTherapy,
    "faers_indication": FaersIndication,
    "rejected_record": DatabaseRejectedRecord,
    "ingestion_issue": IngestionIssue,
}


def _database_counts(
    connection: Connection, member_ids: Mapping[FaersTable, int]
) -> tuple[dict[str, int], dict[str, int]]:
    total = {
        name: int(connection.scalar(select(func.count()).select_from(model)) or 0)
        for name, model in _DATABASE_MODELS.items()
    }
    artifact = {
        "faers_report_version": int(
            connection.scalar(
                select(func.count())
                .select_from(FaersReportVersion)
                .where(FaersReportVersion.source_member_id == member_ids[FaersTable.DEMO])
            )
            or 0
        ),
        "faers_drug_sequence": int(
            connection.scalar(
                select(func.count())
                .select_from(FaersDrugSequence)
                .where(FaersDrugSequence.source_member_id == member_ids[FaersTable.DRUG])
            )
            or 0
        ),
    }
    member_models: dict[str, tuple[Any, FaersTable]] = {
        "faers_drug": (FaersDrug, FaersTable.DRUG),
        "faers_reaction": (FaersReaction, FaersTable.REAC),
        "faers_outcome": (FaersOutcome, FaersTable.OUTC),
        "faers_therapy": (FaersTherapy, FaersTable.THER),
        "faers_indication": (FaersIndication, FaersTable.INDI),
    }
    for name, (model, table) in member_models.items():
        artifact[name] = int(
            connection.scalar(
                select(func.count())
                .select_from(model)
                .where(model.source_member_id == member_ids[table])
            )
            or 0
        )
    artifact["faers_case"] = int(
        connection.scalar(
            select(func.count(func.distinct(FaersReportVersion.case_id))).where(
                FaersReportVersion.source_member_id == member_ids[FaersTable.DEMO]
            )
        )
        or 0
    )
    return artifact, total


def _foreign_key_violations(connection: Connection) -> dict[str, int]:
    checks = {
        "report_without_case": """SELECT COUNT(*) FROM faers_report_version r
            LEFT JOIN faers_case c ON c.case_id = r.case_id WHERE c.case_id IS NULL""",
        "drug_sequence_without_report": """SELECT COUNT(*) FROM faers_drug_sequence d
            LEFT JOIN faers_report_version r ON r.primary_id = d.primary_id
            WHERE r.primary_id IS NULL""",
        "drug_without_sequence": """SELECT COUNT(*) FROM faers_drug d
            LEFT JOIN faers_drug_sequence s
              ON s.primary_id = d.primary_id AND s.drug_seq = d.drug_seq
            WHERE s.primary_id IS NULL""",
        "reaction_without_report": """SELECT COUNT(*) FROM faers_reaction c
            LEFT JOIN faers_report_version r ON r.primary_id = c.primary_id
            WHERE r.primary_id IS NULL""",
        "outcome_without_report": """SELECT COUNT(*) FROM faers_outcome c
            LEFT JOIN faers_report_version r ON r.primary_id = c.primary_id
            WHERE r.primary_id IS NULL""",
        "therapy_without_sequence": """SELECT COUNT(*) FROM faers_therapy c
            LEFT JOIN faers_drug_sequence s
              ON s.primary_id = c.primary_id AND s.drug_seq = c.drug_seq
            WHERE s.primary_id IS NULL""",
        "indication_without_sequence": """SELECT COUNT(*) FROM faers_indication c
            LEFT JOIN faers_drug_sequence s
              ON s.primary_id = c.primary_id AND s.drug_seq = c.drug_seq
            WHERE s.primary_id IS NULL""",
    }
    return {
        name: int(connection.scalar(text(statement)) or 0) for name, statement in checks.items()
    }


def _build_reconciliation(
    engine: Engine,
    *,
    run_id: int,
    status: str,
    no_op: bool,
    manifest: SourceManifest,
    checksum: str,
    batch_size: int,
    configuration: Mapping[str, object],
    member_ids: Mapping[FaersTable, int],
    duration: float,
) -> IngestionReconciliation:
    table_reports: dict[str, TableReconciliation] = {}
    missing_parents: dict[str, int] = {}
    for table in LOAD_ORDER:
        progress = _table_progress(configuration, table)
        previously_existing = progress.accepted_rows if no_op else progress.skipped_rows
        table_reports[table.value] = TableReconciliation(
            source_rows=progress.source_rows,
            expected_source_rows=manifest.scoped_rows[table.value],
            accepted_rows=progress.accepted_rows,
            rejected_rows=progress.rejected_rows,
            inserted_rows=0 if no_op else progress.inserted_rows,
            skipped_rows=progress.accepted_rows if no_op else progress.skipped_rows,
            previously_existing_rows=previously_existing,
            batches=progress.batches,
            complete=progress.complete,
        )
    with engine.connect() as connection:
        artifact_counts, total_counts = _database_counts(connection, member_ids)
        integrity = _foreign_key_violations(connection)
        issue_counts = {
            str(code): int(count)
            for code, count in connection.execute(
                select(IngestionIssue.issue_code, func.count())
                .where(IngestionIssue.ingestion_run_id == run_id)
                .group_by(IngestionIssue.issue_code)
            ).tuples()
        }
    for code in (IssueCode.ORPHAN_REPORT.value, IssueCode.ORPHAN_DRUG_SEQUENCE.value):
        missing_parents[code] = int(issue_counts.get(code, 0))
    duplicate_count = sum(report.previously_existing_rows for report in table_reports.values())
    return IngestionReconciliation(
        run_id=run_id,
        status=status,
        no_op=no_op,
        source_year=manifest.year,
        source_quarter=manifest.quarter,
        archive_filename=manifest.archive_filename,
        archive_sha256=checksum,
        parser_version=PARSER_VERSION,
        schema_version=SCHEMA_VERSION,
        batch_size=batch_size,
        resume_count=_as_int(configuration.get("resume_count", 0)),
        duration_seconds=round(duration, 3),
        tables=table_reports,
        database_rows_for_artifact=artifact_counts,
        database_rows_total=total_counts,
        foreign_key_violations=integrity,
        duplicate_handling={"previously_existing_or_replayed": duplicate_count},
        missing_parent_references=missing_parents,
    )


def ingest_archive(
    engine: Engine,
    archive_path: Path,
    manifest_path: Path,
    *,
    year: int,
    quarter: int,
    batch_size: int = DEFAULT_BATCH_SIZE,
    max_batches: int | None = None,
    require_migration: bool = True,
) -> IngestionReconciliation:
    """Load or resume one explicitly selected and checksummed FAERS quarter."""

    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    if max_batches is not None and max_batches < 1:
        raise ValueError("max_batches must be positive")
    started = time.perf_counter()
    manifest = load_source_manifest(manifest_path)
    inspection, checksum = validate_source(archive_path, manifest, year=year, quarter=quarter)
    _verify_schema(engine, require_migration=require_migration)

    with engine.begin() as connection:
        artifact_id, member_ids, run_id, configuration, already_complete = _register_provenance(
            connection,
            archive_path,
            manifest,
            inspection,
            checksum,
            batch_size,
        )
    del artifact_id
    if already_complete:
        return _build_reconciliation(
            engine,
            run_id=run_id,
            status=IngestionStatus.COMPLETED.value,
            no_op=True,
            manifest=manifest,
            checksum=checksum,
            batch_size=batch_size,
            configuration=configuration,
            member_ids=member_ids,
            duration=time.perf_counter() - started,
        )

    invocation_batches = 0
    try:
        for table in LOAD_ORDER:
            progress = _table_progress(configuration, table)
            if progress.complete:
                continue
            _, events = iter_table_records(archive_path, table, inspection=inspection)
            remaining = (
                event for event in events if event.source_row_number > progress.last_source_row
            )
            for batch in _chunks(remaining, batch_size):
                with engine.begin() as connection:
                    accepted, rejected, inserted, _ = _persist_batch(
                        connection,
                        batch,
                        table=table,
                        run_id=run_id,
                        member_id=member_ids[table],
                        year=year,
                        quarter=quarter,
                    )
                    progress.last_source_row = max(item.source_row_number for item in batch)
                    progress.source_rows += len(batch)
                    progress.accepted_rows += accepted
                    progress.rejected_rows += rejected
                    progress.inserted_rows += inserted
                    progress.skipped_rows += accepted - inserted
                    progress.batches += 1
                    _save_progress(configuration, table, progress)
                    accepted_total, rejected_total, warning_total = _progress_totals(configuration)
                    connection.execute(
                        update(IngestionRun)
                        .where(IngestionRun.id == run_id)
                        .values(
                            configuration=configuration,
                            accepted_records=accepted_total,
                            rejected_records=rejected_total,
                            warning_count=warning_total,
                        )
                    )
                invocation_batches += 1
                if max_batches is not None and invocation_batches >= max_batches:
                    with engine.begin() as connection:
                        connection.execute(
                            update(IngestionRun)
                            .where(IngestionRun.id == run_id)
                            .values(status=IngestionStatus.PAUSED.value)
                        )
                    return _build_reconciliation(
                        engine,
                        run_id=run_id,
                        status=IngestionStatus.PAUSED.value,
                        no_op=False,
                        manifest=manifest,
                        checksum=checksum,
                        batch_size=batch_size,
                        configuration=configuration,
                        member_ids=member_ids,
                        duration=time.perf_counter() - started,
                    )
            progress.complete = True
            _save_progress(configuration, table, progress)
            expected = manifest.scoped_rows[table.value]
            if progress.source_rows != expected:
                raise IngestionValidationError(
                    f"{table.value} source count {progress.source_rows} "
                    f"does not match manifest {expected}"
                )
            with engine.begin() as connection:
                connection.execute(
                    update(IngestionRun)
                    .where(IngestionRun.id == run_id)
                    .values(configuration=configuration)
                )

        accepted_total, rejected_total, warning_total = _progress_totals(configuration)
        with engine.begin() as connection:
            connection.execute(
                update(IngestionRun)
                .where(IngestionRun.id == run_id)
                .values(
                    status=IngestionStatus.COMPLETED.value,
                    finished_at=datetime.now(UTC),
                    configuration=configuration,
                    accepted_records=accepted_total,
                    rejected_records=rejected_total,
                    warning_count=warning_total,
                )
            )
    except Exception as error:
        configuration["last_error"] = f"{type(error).__name__}: {error}"
        try:
            with engine.begin() as connection:
                connection.execute(
                    update(IngestionRun)
                    .where(IngestionRun.id == run_id)
                    .values(
                        status=IngestionStatus.FAILED.value,
                        finished_at=datetime.now(UTC),
                        configuration=configuration,
                    )
                )
        except SQLAlchemyError:
            pass
        raise

    reconciliation = _build_reconciliation(
        engine,
        run_id=run_id,
        status=IngestionStatus.COMPLETED.value,
        no_op=False,
        manifest=manifest,
        checksum=checksum,
        batch_size=batch_size,
        configuration=configuration,
        member_ids=member_ids,
        duration=time.perf_counter() - started,
    )
    if any(reconciliation.foreign_key_violations.values()):
        raise IngestionValidationError("post-load foreign-key reconciliation found orphan rows")
    return reconciliation


def write_reconciliation_reports(
    report: IngestionReconciliation, json_path: Path, markdown_path: Path
) -> None:
    """Atomically write ignored machine- and human-readable reconciliation reports."""

    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_temp = json_path.with_suffix(f"{json_path.suffix}.tmp")
    markdown_temp = markdown_path.with_suffix(f"{markdown_path.suffix}.tmp")
    json_temp.write_text(
        json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    lines = [
        "# FAERS ingestion reconciliation",
        "",
        f"- Status: `{report.status}`",
        f"- Run ID: `{report.run_id}`",
        f"- Source: `{report.source_year} Q{report.source_quarter}`",
        f"- Archive SHA-256: `{report.archive_sha256}`",
        f"- Duration seconds: `{report.duration_seconds}`",
        f"- Completed rerun no-op: `{str(report.no_op).lower()}`",
        "",
        "| Table | Source | Expected | Accepted | Rejected | Inserted | Skipped | Batches |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, item in report.tables.items():
        lines.append(
            f"| {name} | {item.source_rows} | {item.expected_source_rows} | "
            f"{item.accepted_rows} | {item.rejected_rows} | {item.inserted_rows} | "
            f"{item.skipped_rows} | {item.batches} |"
        )
    lines.extend(
        [
            "",
            "Database counts and integrity results are preserved in the JSON report. Counts are "
            "reporting records, not incidence, prevalence, or evidence of causality.",
        ]
    )
    markdown_temp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    json_temp.replace(json_path)
    markdown_temp.replace(markdown_path)
