"""Historical source inventory and loaded-quarter analytics tests."""

from collections.abc import Iterator
from datetime import UTC, datetime
from itertools import count

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Session

from pharmasense.analytics.faers_versions import latest_report_versions_statement
from pharmasense.analytics.historical import (
    SourceQuarter,
    historical_population_filter,
    historical_resolution_summary_statement,
    source_snapshot_inventory_statement,
    successfully_loaded_quarters_statement,
)
from pharmasense.analytics.signals import ContingencyTable, drug_reaction_contingency_statement
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
        seed_historical_population(database_session)
        yield database_session
    engine.dispose()


def seed_historical_population(session: Session) -> None:
    """Create two complete quarters and one provenance-known failed partial quarter."""

    row_numbers = count(2)

    def provenance(
        year: int, quarter: int, status: str
    ) -> tuple[IngestionRun, dict[str, SourceMember]]:
        identity = f"{year}Q{quarter}"
        artifact = SourceArtifact(
            source_name=f"Synthetic {identity} fixture",
            source_system="FAERS",
            source_year=year,
            source_quarter=quarter,
            archive_format="TEST_ONLY",
            source_url=f"https://example.invalid/{identity}.zip",
            retrieved_at=datetime(2026, 11, quarter, tzinfo=UTC),
            filename=f"{identity}.zip",
            storage_path=f"test-only/{identity}.zip",
            byte_size=1,
            sha256=str(quarter) * 64,
        )
        members = {
            table: SourceMember(
                artifact=artifact,
                logical_table=table,
                member_path=f"{identity}/{table.lower()}.txt",
                uncompressed_bytes=1,
                compressed_bytes=1,
                crc32=f"{quarter:08x}",
                header=["SYNTHETIC"],
                row_count=1,
            )
            for table in ("DEMO", "DRUG", "REAC")
        }
        run = IngestionRun(
            artifact=artifact,
            idempotency_key=str(quarter + 4) * 64,
            parser_version="test-only",
            schema_version="20261103_0002",
            status=status,
            started_at=datetime(2026, 11, quarter, tzinfo=UTC),
            finished_at=(
                datetime(2026, 11, quarter, 1, tzinfo=UTC) if status == "COMPLETED" else None
            ),
            accepted_records=0,
            rejected_records=0,
            warning_count=0,
        )
        session.add(run)
        return run, members

    sources = {
        (2023, 1): provenance(2023, 1, "COMPLETED"),
        (2023, 2): provenance(2023, 2, "COMPLETED"),
        (2023, 3): provenance(2023, 3, "FAILED"),
    }

    def add_report(
        year: int,
        quarter: int,
        case_id: str,
        primary_id: str,
        case_version: str,
        drugs: list[str],
        reactions: list[str],
    ) -> None:
        run, members = sources[(year, quarter)]
        case_record = session.get(FaersCase, case_id)
        if case_record is None:
            case_record = FaersCase(case_id=case_id, created_by_run=run)
        report = FaersReportVersion(
            primary_id=primary_id,
            case=case_record,
            case_version=case_version,
            source_year=year,
            source_quarter=quarter,
            source_member=members["DEMO"],
            ingestion_run=run,
            source_row_number=next(row_numbers),
        )
        for sequence_number, drug_name in enumerate(drugs, start=1):
            sequence = FaersDrugSequence(
                primary_id=primary_id,
                drug_seq=str(sequence_number),
                source_member=members["DRUG"],
                ingestion_run=run,
                source_year=year,
                source_quarter=quarter,
            )
            sequence.drugs.append(
                FaersDrug(
                    source_case_id=case_id,
                    role_cod="PS",
                    drugname=drug_name,
                    source_member=members["DRUG"],
                    ingestion_run=run,
                    source_row_number=next(row_numbers),
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
                    source_row_number=next(row_numbers),
                )
            )
        session.add(report)
        session.flush()

    add_report(2023, 1, "CASE-A", "A-1", "1", ["TARGET"], ["EVENT"])
    add_report(2023, 1, "CASE-B", "B-1", "1", ["OTHER"], ["OTHER EVENT"])
    add_report(2023, 1, "CASE-INVALID", "I-X", "invalid", ["TARGET"], ["EVENT"])
    add_report(2023, 2, "CASE-A", "A-2", "2", ["TARGET", "TARGET"], ["EVENT", "EVENT"])
    add_report(2023, 2, "CASE-B", "B-2", "2", ["OTHER"], ["EVENT"])
    add_report(2023, 2, "CASE-TIE", "T-1", "1", ["TARGET"], ["EVENT"])
    add_report(2023, 2, "CASE-TIE", "T-01", "01", ["TARGET"], ["EVENT"])
    add_report(2023, 3, "CASE-FAILED", "F-1", "1", ["TARGET"], ["EVENT"])
    session.commit()


def test_source_quarter_parsing_and_range_validation() -> None:
    assert SourceQuarter.parse("2023Q4") == SourceQuarter(2023, 4)
    assert SourceQuarter(2024, 1).ordinal == SourceQuarter(2023, 4).ordinal + 1
    with pytest.raises(ValueError, match="YYYYQ1"):
        SourceQuarter.parse("2023-Q4")
    with pytest.raises(ValueError, match="between 1 and 4"):
        SourceQuarter(2023, 5)


def test_inventory_distinguishes_known_persisted_and_successfully_loaded_sources(
    session: Session,
) -> None:
    rows = session.execute(source_snapshot_inventory_statement()).mappings().all()

    assert [(row["source_year"], row["source_quarter"]) for row in rows] == [
        (2023, 1),
        (2023, 2),
        (2023, 3),
    ]
    assert rows[0]["persisted_report_count"] == 3
    assert rows[0]["successfully_loaded_report_count"] == 3
    assert rows[1]["successfully_loaded_report_count"] == 4
    assert rows[1]["successfully_loaded_case_count"] == 3
    assert rows[2]["persisted_report_count"] == 1
    assert rows[2]["successfully_loaded_report_count"] == 0
    assert rows[2]["completed_ingestion_runs"] == 0


def test_loaded_quarter_selection_is_completed_bounded_and_deterministic(session: Session) -> None:
    rows = session.execute(
        successfully_loaded_quarters_statement(SourceQuarter(2023, 1), SourceQuarter(2023, 4))
    ).all()

    assert [tuple(row) for row in rows] == [(2023, 1), (2023, 2)]


def test_historical_filter_resolves_across_selected_quarters_without_double_counting(
    session: Session,
) -> None:
    quarters = (SourceQuarter(2023, 1), SourceQuarter(2023, 2))
    latest = session.scalars(
        latest_report_versions_statement(historical_population_filter(quarters))
    ).all()
    summary = session.execute(historical_resolution_summary_statement(quarters)).mappings().one()

    assert {(report.case_id, report.primary_id) for report in latest} == {
        ("CASE-A", "A-2"),
        ("CASE-B", "B-2"),
    }
    assert summary == {
        "resolved_report_count": 2,
        "resolved_case_count": 2,
        "excluded_invalid_version_case_count": 1,
        "excluded_version_tie_case_count": 1,
    }
    assert "F-1" in {
        report.primary_id for report in session.scalars(latest_report_versions_statement())
    }


def test_quarter_contingencies_deduplicate_rows_and_resolve_each_quarter(session: Session) -> None:
    q1 = historical_population_filter((SourceQuarter(2023, 1),))
    q2 = historical_population_filter((SourceQuarter(2023, 2),))

    first = (
        session.execute(drug_reaction_contingency_statement("TARGET", "EVENT", q1)).mappings().one()
    )
    second = (
        session.execute(drug_reaction_contingency_statement("TARGET", "EVENT", q2)).mappings().one()
    )

    assert ContingencyTable(
        a=first["a"], b=first["b"], c=first["c"], d=first["d"]
    ) == ContingencyTable(a=1, b=0, c=0, d=1)
    assert ContingencyTable(
        a=second["a"], b=second["b"], c=second["c"], d=second["d"]
    ) == ContingencyTable(a=1, b=0, c=1, d=0)
    assert first["population_size"] == second["population_size"] == 2


def test_historical_queries_compile_for_mysql() -> None:
    dialect = mysql.dialect()  # type: ignore[no-untyped-call]
    population = historical_population_filter((SourceQuarter(2023, 4),))

    inventory_sql = str(source_snapshot_inventory_statement().compile(dialect=dialect))
    latest_sql = str(latest_report_versions_statement(population).compile(dialect=dialect))

    assert "source_artifact_report_counts" in inventory_sql
    assert "COMPLETED" not in latest_sql
    assert latest_report_versions_statement(population).compile(dialect=dialect).params
