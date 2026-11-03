"""Constraint and relationship tests using clearly synthetic FAERS-shaped records."""

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import Engine, create_engine, event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pharmasense.db.base import Base
from pharmasense.db.models import (
    FaersCase,
    FaersDrug,
    FaersDrugSequence,
    FaersIndication,
    FaersOutcome,
    FaersReaction,
    FaersReportVersion,
    FaersTherapy,
    IngestionRun,
    SourceArtifact,
    SourceMember,
)


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection: object, _connection_record: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    with Session(engine) as database_session:
        yield database_session
    engine.dispose()


def add_provenance(session: Session) -> tuple[IngestionRun, dict[str, SourceMember]]:
    artifact = SourceArtifact(
        id=1,
        source_name="Synthetic test artifact",
        source_system="FAERS",
        source_year=2023,
        source_quarter=4,
        archive_format="ASCII_ZIP",
        source_url="https://example.invalid/synthetic.zip",
        retrieved_at=datetime(2026, 11, 3, tzinfo=UTC),
        filename="synthetic.zip",
        storage_path="test-only/synthetic.zip",
        byte_size=1,
        sha256="a" * 64,
    )
    table_names = ("DEMO", "DRUG", "REAC", "OUTC", "THER", "INDI")
    members = {
        table: SourceMember(
            id=index,
            artifact=artifact,
            logical_table=table,
            member_path=f"synthetic/{table.lower()}.txt",
            uncompressed_bytes=1,
            compressed_bytes=1,
            crc32=f"{index:08x}",
            header=["SYNTHETIC"],
            row_count=1,
        )
        for index, table in enumerate(table_names, start=1)
    }
    run = IngestionRun(
        id=1,
        artifact=artifact,
        idempotency_key="b" * 64,
        parser_version="test-only",
        schema_version="20261103_0002",
        status="COMPLETED",
        started_at=datetime(2026, 11, 3, tzinfo=UTC),
        accepted_records=0,
        rejected_records=0,
        warning_count=0,
    )
    session.add_all([artifact, *members.values(), run])
    session.flush()
    return run, members


def add_report(
    session: Session,
    run: IngestionRun,
    members: dict[str, SourceMember],
    *,
    primary_id: str,
    case_version: str,
    source_row_number: int,
    case: FaersCase | None = None,
) -> FaersReportVersion:
    if case is None:
        case = FaersCase(case_id="SYNTHETIC-CASE", created_by_run=run)
        session.add(case)
    report = FaersReportVersion(
        primary_id=primary_id,
        case=case,
        case_version=case_version,
        source_year=2023,
        source_quarter=4,
        source_member=members["DEMO"],
        ingestion_run=run,
        source_row_number=source_row_number,
    )
    session.add(report)
    session.flush()
    return report


def test_preserves_multiple_historical_versions_for_one_case(session: Session) -> None:
    run, members = add_provenance(session)
    case = FaersCase(case_id="SYNTHETIC-CASE", created_by_run=run)
    first = add_report(
        session,
        run,
        members,
        primary_id="SYNTHETIC-PRIMARY-1",
        case_version="1",
        source_row_number=2,
        case=case,
    )
    follow_up = add_report(
        session,
        run,
        members,
        primary_id="SYNTHETIC-PRIMARY-2",
        case_version="2",
        source_row_number=3,
        case=case,
    )
    session.commit()

    stored_case = session.get(FaersCase, "SYNTHETIC-CASE")
    assert stored_case is not None
    assert [item.primary_id for item in stored_case.report_versions] == [
        first.primary_id,
        follow_up.primary_id,
    ]
    assert first.source_member.artifact.sha256 == "a" * 64
    assert first.ingestion_run.idempotency_key == "b" * 64


def test_repeated_drug_sequence_rows_and_child_grains_are_preserved(session: Session) -> None:
    run, members = add_provenance(session)
    report = add_report(
        session,
        run,
        members,
        primary_id="SYNTHETIC-PRIMARY-1",
        case_version="1",
        source_row_number=2,
    )
    sequence = FaersDrugSequence(
        primary_id=report.primary_id,
        drug_seq="1",
        source_member=members["DRUG"],
        ingestion_run=run,
        source_year=2023,
        source_quarter=4,
    )
    sequence.drugs.extend(
        [
            FaersDrug(
                id=1,
                source_case_id="SYNTHETIC-CASE",
                role_cod="PS",
                drugname="SYNTHETIC DRUG",
                source_member=members["DRUG"],
                ingestion_run=run,
                source_row_number=2,
            ),
            FaersDrug(
                id=2,
                source_case_id="SYNTHETIC-CASE",
                role_cod="PS",
                drugname="SYNTHETIC DRUG",
                dose_vbm="SYNTHETIC SECOND DETAIL",
                source_member=members["DRUG"],
                ingestion_run=run,
                source_row_number=3,
            ),
        ]
    )
    sequence.therapies.append(
        FaersTherapy(
            id=1,
            source_case_id="SYNTHETIC-CASE",
            start_dt="2023",
            source_member=members["THER"],
            ingestion_run=run,
            source_row_number=2,
        )
    )
    sequence.indications.append(
        FaersIndication(
            id=1,
            source_case_id="SYNTHETIC-CASE",
            indi_pt="SYNTHETIC INDICATION",
            source_member=members["INDI"],
            ingestion_run=run,
            source_row_number=2,
        )
    )
    report.reactions.append(
        FaersReaction(
            id=1,
            source_case_id="SYNTHETIC-CASE",
            pt="SYNTHETIC REACTION",
            source_member=members["REAC"],
            ingestion_run=run,
            source_row_number=2,
        )
    )
    report.outcomes.append(
        FaersOutcome(
            id=1,
            source_case_id="SYNTHETIC-CASE",
            outc_cod="OT",
            source_member=members["OUTC"],
            ingestion_run=run,
            source_row_number=2,
        )
    )
    report.drug_sequences.append(sequence)
    session.commit()

    stored = session.get(FaersDrugSequence, (report.primary_id, "1"))
    assert stored is not None
    assert len(stored.drugs) == 2
    assert stored.drugs[0].source_case_id == "SYNTHETIC-CASE"
    assert stored.therapies[0].drug_sequence is stored
    assert stored.indications[0].drug_sequence is stored
    assert report.reactions[0].report_version is report
    assert report.outcomes[0].report_version is report


def test_duplicate_source_row_and_run_idempotency_are_rejected(session: Session) -> None:
    run, members = add_provenance(session)
    add_report(
        session,
        run,
        members,
        primary_id="SYNTHETIC-PRIMARY-1",
        case_version="1",
        source_row_number=2,
    )
    session.add(
        FaersReportVersion(
            primary_id="SYNTHETIC-PRIMARY-2",
            case_id="SYNTHETIC-CASE",
            case_version="2",
            source_year=2023,
            source_quarter=4,
            source_member_id=members["DEMO"].id,
            ingestion_run_id=run.id,
            source_row_number=2,
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()

    duplicate_run = IngestionRun(
        id=2,
        artifact_id=1,
        idempotency_key="b" * 64,
        parser_version="test-only",
        schema_version="20261103_0002",
        status="STARTED",
        started_at=datetime(2026, 11, 3, tzinfo=UTC),
        accepted_records=0,
        rejected_records=0,
        warning_count=0,
    )
    session.add(duplicate_run)
    with pytest.raises(IntegrityError):
        session.commit()


def test_orphan_child_and_parent_deletion_are_rejected(session: Session) -> None:
    run, members = add_provenance(session)
    report = add_report(
        session,
        run,
        members,
        primary_id="SYNTHETIC-PRIMARY-1",
        case_version="1",
        source_row_number=2,
    )
    session.commit()

    session.add(
        FaersTherapy(
            id=1,
            primary_id=report.primary_id,
            source_case_id="SYNTHETIC-CASE",
            drug_seq="MISSING",
            source_member_id=members["THER"].id,
            ingestion_run_id=run.id,
            source_row_number=2,
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()

    artifact = session.get(SourceArtifact, 1)
    assert artifact is not None
    session.delete(artifact)
    with pytest.raises(IntegrityError):
        session.commit()


def test_schema_contains_only_expected_phase_1c_tables() -> None:
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
    assert set(Base.metadata.tables) == expected


def test_sqlite_fixture_enables_foreign_keys(session: Session) -> None:
    engine = session.get_bind()
    assert isinstance(engine, Engine)
    assert session.scalar(select(1)) == 1
