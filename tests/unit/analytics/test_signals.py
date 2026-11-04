"""Statistical signal foundation tests using synthetic FAERS-shaped records."""

from collections.abc import Iterator
from datetime import UTC, datetime
from itertools import count

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.dialects import mysql
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from pharmasense.analytics.prioritization import (
    SignalThresholds,
    signal_candidate_contingencies_statement,
)
from pharmasense.analytics.signals import (
    ContingencyTable,
    UndefinedMetricReason,
    calculate_disproportionality,
    drug_reaction_contingency_statement,
    observed_drug_reaction_contingencies_statement,
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
        seed_signal_population(database_session)
        yield database_session
    engine.dispose()


def seed_signal_population(session: Session) -> None:
    """Create five resolved reports plus excluded history, invalid versions, and a tie."""

    artifact = SourceArtifact(
        source_name="Synthetic Phase 2C fixture",
        source_system="FAERS",
        source_year=2023,
        source_quarter=4,
        archive_format="TEST_ONLY",
        source_url="https://example.invalid/phase-2c.zip",
        retrieved_at=datetime(2026, 11, 4, tzinfo=UTC),
        filename="phase-2c.zip",
        storage_path="test-only/phase-2c.zip",
        byte_size=1,
        sha256="1" * 64,
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
        idempotency_key="2" * 64,
        parser_version="test-only",
        schema_version="20261103_0002",
        status="COMPLETED",
        started_at=datetime(2026, 11, 4, tzinfo=UTC),
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

    add_report("CASE-A", "A-1", "1", ["TARGET"], ["EVENT"])
    add_report(
        "CASE-A",
        "A-2",
        "2",
        ["TARGET", "TARGET", "OTHER"],
        ["EVENT", "EVENT", "OTHER EVENT"],
    )
    add_report("CASE-B", "B-1", "1", ["TARGET"], ["OTHER EVENT"])
    add_report("CASE-C", "C-1", "1", ["OTHER"], ["EVENT"])
    add_report("CASE-D", "D-1", "1", ["OTHER"], ["OTHER EVENT"])
    add_report("CASE-E", "E-1", "1", [], [])
    add_report("CASE-INVALID", "I-X", "unexpected", ["TARGET"], ["EVENT"])
    add_report("CASE-TIE", "T-2", "2", ["TARGET"], ["EVENT"])
    add_report("CASE-TIE", "T-02", "02", ["TARGET"], ["EVENT"])
    session.commit()


def _table_from_row(row: RowMapping) -> ContingencyTable:
    return ContingencyTable(
        a=int(row["a"]),
        b=int(row["b"]),
        c=int(row["c"]),
        d=int(row["d"]),
    )


def test_specific_pair_query_counts_each_resolved_latest_report_once(session: Session) -> None:
    before = session.scalar(select(func.count()).select_from(FaersReportVersion))

    row = session.execute(drug_reaction_contingency_statement("TARGET", "EVENT")).mappings().one()
    metrics = calculate_disproportionality(_table_from_row(row))

    assert row["population_size"] == 5
    assert _table_from_row(row) == ContingencyTable(a=1, b=1, c=1, d=2)
    assert metrics.prr.value == pytest.approx(1.5)
    assert metrics.ror.value == pytest.approx(2.0)
    assert session.scalar(select(func.count()).select_from(FaersReportVersion)) == before == 9


def test_observed_pair_query_is_composable_and_matches_specific_pair(session: Session) -> None:
    contingencies = observed_drug_reaction_contingencies_statement().subquery()
    statement = select(contingencies).where(
        contingencies.c.drug_name == "TARGET",
        contingencies.c.reaction_term == "EVENT",
    )

    row = session.execute(statement).mappings().one()

    assert row["population_size"] == 5
    assert _table_from_row(row) == ContingencyTable(a=1, b=1, c=1, d=2)


def test_prr_and_ror_match_expected_normal_table() -> None:
    metrics = calculate_disproportionality(ContingencyTable(a=20, b=80, c=10, d=890))

    assert metrics.prr.value == pytest.approx(18.0)
    assert metrics.ror.value == pytest.approx(22.25)
    assert metrics.prr.undefined_reason is None
    assert metrics.ror.undefined_reason is None


def test_zero_numerator_is_zero_without_continuity_correction() -> None:
    metrics = calculate_disproportionality(ContingencyTable(a=0, b=2, c=1, d=2))

    assert metrics.prr.value == 0.0
    assert metrics.ror.value == 0.0


def test_zero_denominators_have_explicit_undefined_reasons() -> None:
    no_comparator_events = calculate_disproportionality(ContingencyTable(a=1, b=1, c=0, d=3))
    no_drug_non_events = calculate_disproportionality(ContingencyTable(a=1, b=0, c=1, d=3))

    assert no_comparator_events.prr.value is None
    assert (
        no_comparator_events.prr.undefined_reason
        == UndefinedMetricReason.ZERO_COMPARATOR_REACTION_COUNT
    )
    assert no_comparator_events.ror.value is None
    assert (
        no_comparator_events.ror.undefined_reason
        == UndefinedMetricReason.ZERO_NON_DRUG_REACTION_COUNT
    )
    assert no_drug_non_events.prr.is_defined
    assert (
        no_drug_non_events.ror.undefined_reason
        == UndefinedMetricReason.ZERO_DRUG_NON_REACTION_COUNT
    )


def test_empty_database_returns_zero_table_and_undefined_metrics() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as empty_session:
            row = (
                empty_session.execute(drug_reaction_contingency_statement("TARGET", "EVENT"))
                .mappings()
                .one()
            )
            observed = empty_session.execute(observed_drug_reaction_contingencies_statement()).all()
    finally:
        engine.dispose()

    metrics = calculate_disproportionality(_table_from_row(row))
    assert row["population_size"] == 0
    assert observed == []
    assert metrics.contingency == ContingencyTable(a=0, b=0, c=0, d=0)
    assert metrics.prr.undefined_reason == UndefinedMetricReason.EMPTY_POPULATION
    assert metrics.ror.undefined_reason == UndefinedMetricReason.EMPTY_POPULATION


def test_invalid_and_impossible_contingency_counts_are_rejected() -> None:
    with pytest.raises(ValueError, match="non-negative integer"):
        ContingencyTable(a=-1, b=0, c=0, d=0)
    with pytest.raises(ValueError, match="pair report count"):
        ContingencyTable.from_margins(
            population_size=10,
            drug_report_count=2,
            reaction_report_count=3,
            pair_report_count=4,
        )
    with pytest.raises(ValueError, match="d must be"):
        ContingencyTable.from_margins(
            population_size=3,
            drug_report_count=2,
            reaction_report_count=2,
            pair_report_count=0,
        )


def test_signal_statements_compile_for_mysql_with_bound_filters() -> None:
    dialect = mysql.dialect()  # type: ignore[no-untyped-call]
    selected = drug_reaction_contingency_statement("TARGET", "EVENT")
    selected_compiled = selected.compile(dialect=dialect)
    observed_sql = str(observed_drug_reaction_contingencies_statement().compile(dialect=dialect))
    candidate_sql = str(
        signal_candidate_contingencies_statement(
            SignalThresholds(minimum_pair_reports=2, minimum_population=5)
        ).compile(dialect=dialect)
    )

    assert "TARGET" not in str(selected_compiled)
    assert "EVENT" not in str(selected_compiled)
    assert selected_compiled.params
    assert "resolved_latest_report_versions" in observed_sql
    assert "drug_report_presence" in observed_sql
    assert "observed_signal_contingencies" in candidate_sql


def test_candidate_query_reuses_resolved_deduplicated_contingencies(session: Session) -> None:
    rows = session.execute(
        signal_candidate_contingencies_statement(
            SignalThresholds(minimum_pair_reports=2, minimum_population=5)
        )
    ).mappings()

    assert {
        (row["drug_name"], row["reaction_term"], row["population_size"], row["a"]) for row in rows
    } == {
        ("OTHER", "EVENT", 5, 2),
        ("OTHER", "OTHER EVENT", 5, 2),
        ("TARGET", "OTHER EVENT", 5, 2),
    }
    assert (
        session.execute(
            signal_candidate_contingencies_statement(
                SignalThresholds(minimum_pair_reports=1, minimum_population=6)
            )
        ).all()
        == []
    )
