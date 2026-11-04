"""Drug-reaction analytics tests using clearly synthetic FAERS-shaped records."""

from collections.abc import Iterator
from datetime import UTC, datetime
from itertools import count

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Session

from pharmasense.analytics.drug_reactions import (
    drug_reaction_summary_statement,
    drug_summary_statement,
    most_reported_reactions_for_drug_statement,
)
from pharmasense.db.base import Base
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


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as database_session:
        seed_analytics_population(database_session)
        yield database_session
    engine.dispose()


def seed_analytics_population(session: Session) -> None:
    """Create resolved, invalid, and tied synthetic cases with repeated child values."""

    artifact = SourceArtifact(
        source_name="Synthetic Phase 2B fixture",
        source_system="FAERS",
        source_year=2023,
        source_quarter=4,
        archive_format="TEST_ONLY",
        source_url="https://example.invalid/phase-2b.zip",
        retrieved_at=datetime(2026, 11, 3, tzinfo=UTC),
        filename="phase-2b.zip",
        storage_path="test-only/phase-2b.zip",
        byte_size=1,
        sha256="e" * 64,
    )
    members = {
        table: SourceMember(
            artifact=artifact,
            logical_table=table,
            member_path=f"synthetic/{table.lower()}.txt",
            uncompressed_bytes=1,
            compressed_bytes=1,
            crc32=f"{index:08x}",
            header=["SYNTHETIC"],
            row_count=1,
        )
        for index, table in enumerate(("DEMO", "DRUG", "REAC"), start=1)
    }
    run = IngestionRun(
        artifact=artifact,
        idempotency_key="f" * 64,
        parser_version="test-only",
        schema_version="20261103_0002",
        status="COMPLETED",
        started_at=datetime(2026, 11, 3, tzinfo=UTC),
        accepted_records=0,
        rejected_records=0,
        warning_count=0,
    )
    row_numbers = {table: count(2) for table in members}

    def add_report(
        case_id: str,
        primary_id: str,
        case_version: str,
        drugs: list[str],
        reactions: list[str],
    ) -> None:
        case_record = session.get(FaersCase, case_id)
        if case_record is None:
            case_record = FaersCase(case_id=case_id, created_by_run=run)
        report = FaersReportVersion(
            primary_id=primary_id,
            case=case_record,
            case_version=case_version,
            source_year=2023,
            source_quarter=4,
            source_member=members["DEMO"],
            ingestion_run=run,
            source_row_number=next(row_numbers["DEMO"]),
        )
        for sequence_number, drug_name in enumerate(drugs, start=1):
            sequence = FaersDrugSequence(
                primary_id=primary_id,
                drug_seq=str(sequence_number),
                source_member=members["DRUG"],
                ingestion_run=run,
                source_year=2023,
                source_quarter=4,
            )
            sequence.drugs.append(
                FaersDrug(
                    source_case_id=case_id,
                    role_cod="PS",
                    drugname=drug_name,
                    source_member=members["DRUG"],
                    ingestion_run=run,
                    source_row_number=next(row_numbers["DRUG"]),
                )
            )
            report.drug_sequences.append(sequence)
        for reaction_term in reactions:
            report.reactions.append(
                FaersReaction(
                    source_case_id=case_id,
                    pt=reaction_term,
                    source_member=members["REAC"],
                    ingestion_run=run,
                    source_row_number=next(row_numbers["REAC"]),
                )
            )
        session.add(report)
        session.flush()

    add_report("CASE-A", "A-1", "1", ["OLD DRUG"], ["OLD REACTION"])
    add_report(
        "CASE-A",
        "A-2",
        "2",
        ["ALPHA", "ALPHA", "BETA"],
        ["HEADACHE", "HEADACHE", "NAUSEA"],
    )
    add_report("CASE-B", "B-1", "1", ["ALPHA", "GAMMA"], ["HEADACHE", "RASH", "RASH"])
    add_report("CASE-EMPTY", "E-1", "1", [], [])
    add_report("CASE-INVALID", "I-X", "unexpected", ["EXCLUDED"], ["EXCLUDED"])
    add_report("CASE-TIE", "T-2", "2", ["EXCLUDED"], ["EXCLUDED"])
    add_report("CASE-TIE", "T-02", "02", ["EXCLUDED"], ["EXCLUDED"])
    session.commit()


def test_drug_summary_uses_latest_resolved_reports_and_deduplicates_names(
    session: Session,
) -> None:
    before = session.scalar(select(func.count()).select_from(FaersDrug))

    rows = session.execute(drug_summary_statement()).mappings().all()

    assert [(row["drug_name"], row["report_count"], row["case_count"]) for row in rows] == [
        ("ALPHA", 2, 2),
        ("BETA", 1, 1),
        ("GAMMA", 1, 1),
    ]
    assert session.scalar(select(func.count()).select_from(FaersDrug)) == before == 9


def test_drug_reaction_summary_avoids_many_to_many_count_inflation(session: Session) -> None:
    rows = session.execute(drug_reaction_summary_statement()).mappings().all()

    assert [
        (row["drug_name"], row["reaction_term"], row["report_count"], row["case_count"])
        for row in rows
    ] == [
        ("ALPHA", "HEADACHE", 2, 2),
        ("ALPHA", "NAUSEA", 1, 1),
        ("ALPHA", "RASH", 1, 1),
        ("BETA", "HEADACHE", 1, 1),
        ("BETA", "NAUSEA", 1, 1),
        ("GAMMA", "HEADACHE", 1, 1),
        ("GAMMA", "RASH", 1, 1),
    ]


def test_most_reported_reactions_filters_exact_drug_name_and_limits(session: Session) -> None:
    rows = session.execute(most_reported_reactions_for_drug_statement("ALPHA", limit=2)).mappings()

    assert [(row["reaction_term"], row["report_count"], row["case_count"]) for row in rows] == [
        ("HEADACHE", 2, 2),
        ("NAUSEA", 1, 1),
    ]


def test_selected_drug_with_no_resolved_reports_returns_empty_result(session: Session) -> None:
    rows = session.execute(most_reported_reactions_for_drug_statement("EXCLUDED")).all()

    assert rows == []


def test_non_positive_reaction_limit_is_rejected() -> None:
    with pytest.raises(ValueError, match="positive integer"):
        most_reported_reactions_for_drug_statement("ALPHA", limit=0)


def test_statements_compile_for_mysql_with_bound_drug_filter() -> None:
    dialect = mysql.dialect()  # type: ignore[no-untyped-call]
    drug_sql = str(drug_summary_statement().compile(dialect=dialect))
    pair_sql = str(drug_reaction_summary_statement().compile(dialect=dialect))
    selected = most_reported_reactions_for_drug_statement("ALPHA", limit=5)
    selected_sql = str(selected.compile(dialect=dialect))

    assert "resolved_latest_report_versions" in drug_sql
    assert "SELECT DISTINCT" in pair_sql
    assert "ALPHA" not in selected_sql
    assert selected.compile(dialect=dialect).params
