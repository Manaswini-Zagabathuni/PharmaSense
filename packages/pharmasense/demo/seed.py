"""Idempotent, synthetic-only data seed for local dashboard demonstrations."""

from __future__ import annotations

import argparse
import hashlib
import zlib
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from pharmasense.config.settings import get_settings
from pharmasense.db.engine import build_engine
from pharmasense.db.models import (
    FaersCase,
    FaersDrug,
    FaersDrugSequence,
    FaersReaction,
    FaersReportVersion,
    IngestionRun,
    SourceArtifact,
    SourceMember,
)

DEMO_ARTIFACT_MARKER = b"pharmasense-phase-4a-synthetic-demo-v1"
DEMO_ARTIFACT_SHA256 = hashlib.sha256(DEMO_ARTIFACT_MARKER).hexdigest()
DEMO_IDEMPOTENCY_KEY = hashlib.sha256(DEMO_ARTIFACT_MARKER + b":ingestion").hexdigest()
DEMO_DRUG_A = "DEMO DRUG ALPHA"
DEMO_DRUG_B = "DEMO DRUG BETA"
DEMO_REACTION_A = "DEMO REACTION ALPHA"
DEMO_REACTION_B = "DEMO REACTION BETA"
_DEMO_REPORT_COUNT = 20
_DEMO_TIMESTAMP = datetime(2099, 1, 1, tzinfo=UTC)


@dataclass(frozen=True)
class DemoSeedResult:
    """Outcome of an idempotent demonstration seed attempt."""

    created: bool
    report_count: int
    message: str


def seed_demo_data(engine: Engine) -> DemoSeedResult:
    """Insert one deterministic synthetic population in a single transaction.

    The marker checksum makes reruns a no-op. These records are deliberately named as demo data,
    use a non-FAERS source system, and must never be represented as FDA observations.
    """

    with Session(engine) as session, session.begin():
        existing = session.scalar(
            select(SourceArtifact.id).where(SourceArtifact.sha256 == DEMO_ARTIFACT_SHA256)
        )
        if existing is not None:
            return DemoSeedResult(
                created=False,
                report_count=_DEMO_REPORT_COUNT,
                message="Synthetic demonstration data is already present; no changes were made.",
            )

        artifact = SourceArtifact(
            source_name="PharmaSense synthetic demonstration population",
            source_system="PHARMASENSE_DEMO",
            source_year=2099,
            source_quarter=1,
            archive_format="SYNTHETIC_EMBEDDED",
            source_url="urn:pharmasense:demo:phase-4a:v1",
            landing_page_url=None,
            posted_date=None,
            retrieved_at=_DEMO_TIMESTAMP,
            filename="pharmasense-demo-v1",
            storage_path="embedded://pharmasense/demo/v1",
            byte_size=len(DEMO_ARTIFACT_MARKER),
            sha256=DEMO_ARTIFACT_SHA256,
        )
        members = {
            name: _source_member(artifact, name, row_count=_DEMO_REPORT_COUNT)
            for name in ("DEMO", "DRUG", "REAC")
        }
        run = IngestionRun(
            artifact=artifact,
            idempotency_key=DEMO_IDEMPOTENCY_KEY,
            parser_version="synthetic-demo-v1",
            schema_version="20261103_0002",
            status="COMPLETED",
            code_revision=None,
            configuration={
                "dataset_kind": "synthetic_demonstration_only",
                "fda_data": False,
            },
            started_at=_DEMO_TIMESTAMP,
            finished_at=_DEMO_TIMESTAMP,
            accepted_records=_DEMO_REPORT_COUNT * 3,
            rejected_records=0,
            warning_count=0,
            report_id="phase-4a-demo-v1",
        )
        session.add_all([artifact, *members.values(), run])
        session.flush()

        for index in range(1, _DEMO_REPORT_COUNT + 1):
            drug_name, reaction_term = _demo_pair(index)
            case_id = f"DEMO-CASE-{index:04d}"
            primary_id = f"DEMO-PRIMARY-{index:04d}"
            report = FaersReportVersion(
                primary_id=primary_id,
                case=FaersCase(case_id=case_id, created_by_run=run),
                case_version="1",
                source_year=2099,
                source_quarter=1,
                source_member=members["DEMO"],
                ingestion_run=run,
                source_row_number=index + 1,
                source_extras={"synthetic_demo": True},
            )
            sequence = FaersDrugSequence(
                primary_id=primary_id,
                drug_seq="1",
                source_member=members["DRUG"],
                ingestion_run=run,
                source_year=2099,
                source_quarter=1,
            )
            sequence.drugs.append(
                FaersDrug(
                    primary_id=primary_id,
                    source_case_id=case_id,
                    drug_seq="1",
                    role_cod="PS",
                    drugname=drug_name,
                    source_member=members["DRUG"],
                    ingestion_run=run,
                    source_row_number=index + 1,
                    source_extras={"synthetic_demo": True},
                )
            )
            report.drug_sequences.append(sequence)
            report.reactions.append(
                FaersReaction(
                    primary_id=primary_id,
                    source_case_id=case_id,
                    pt=reaction_term,
                    source_member=members["REAC"],
                    ingestion_run=run,
                    source_row_number=index + 1,
                    source_extras={"synthetic_demo": True},
                )
            )
            session.add(report)

    return DemoSeedResult(
        created=True,
        report_count=_DEMO_REPORT_COUNT,
        message="Created 20 synthetic demonstration reports. These are not FDA data.",
    )


def _source_member(artifact: SourceArtifact, logical_table: str, *, row_count: int) -> SourceMember:
    payload = f"pharmasense-demo-v1:{logical_table}:{row_count}".encode()
    return SourceMember(
        artifact=artifact,
        logical_table=logical_table,
        member_path=f"embedded/demo/{logical_table.lower()}.txt",
        uncompressed_bytes=len(payload),
        compressed_bytes=len(payload),
        crc32=f"{zlib.crc32(payload):08x}",
        sha256=hashlib.sha256(payload).hexdigest(),
        header=_member_header(logical_table),
        row_count=row_count,
    )


def _member_header(logical_table: str) -> list[str]:
    if logical_table == "DEMO":
        return ["PRIMARYID", "CASEID", "CASEVERSION"]
    if logical_table == "DRUG":
        return ["PRIMARYID", "CASEID", "DRUG_SEQ", "ROLE_COD", "DRUGNAME"]
    return ["PRIMARYID", "CASEID", "PT"]


def _demo_pair(index: int) -> tuple[str, str]:
    if index <= 8:
        return DEMO_DRUG_A, DEMO_REACTION_A
    if index <= 10:
        return DEMO_DRUG_A, DEMO_REACTION_B
    if index <= 12:
        return DEMO_DRUG_B, DEMO_REACTION_A
    return DEMO_DRUG_B, DEMO_REACTION_B


def main() -> None:
    """Seed the configured non-production database after explicit confirmation."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--confirm-synthetic",
        action="store_true",
        help="confirm that demonstration-only records should be inserted",
    )
    args = parser.parse_args()
    if not args.confirm_synthetic:
        parser.error("--confirm-synthetic is required")

    settings = get_settings()
    if settings.app_environment == "production":
        parser.error("synthetic demonstration data cannot be seeded in production")
    database_url = settings.sqlalchemy_url()
    if database_url is None:
        parser.error("database configuration is incomplete")

    engine = build_engine(database_url)
    try:
        result = seed_demo_data(engine)
    finally:
        engine.dispose()
    print(result.message)


if __name__ == "__main__":  # pragma: no cover
    main()
