"""Strict latest-version resolution tests using synthetic report metadata."""

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Session

from pharmasense.analytics.faers_versions import (
    ReportVersionResolutionStatus,
    latest_report_versions_statement,
    report_version_resolution_statement,
)
from pharmasense.db.base import Base
from pharmasense.db.models import (
    FaersCase,
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
        seed_report_versions(database_session)
        yield database_session
    engine.dispose()


def seed_report_versions(session: Session) -> None:
    """Insert test-only cases covering numeric order, invalid values, and numeric ties."""

    artifact = SourceArtifact(
        source_name="Synthetic analytics fixture",
        source_system="FAERS",
        source_year=2023,
        source_quarter=4,
        archive_format="TEST_ONLY",
        source_url="https://example.invalid/analytics-fixture.zip",
        retrieved_at=datetime(2026, 11, 3, tzinfo=UTC),
        filename="analytics-fixture.zip",
        storage_path="test-only/analytics-fixture.zip",
        byte_size=1,
        sha256="c" * 64,
    )
    member = SourceMember(
        artifact=artifact,
        logical_table="DEMO",
        member_path="synthetic/demo.txt",
        uncompressed_bytes=1,
        compressed_bytes=1,
        crc32="00000001",
        header=["SYNTHETIC"],
        row_count=9,
    )
    run = IngestionRun(
        artifact=artifact,
        idempotency_key="d" * 64,
        parser_version="test-only",
        schema_version="20261103_0002",
        status="COMPLETED",
        started_at=datetime(2026, 11, 3, tzinfo=UTC),
        accepted_records=9,
        rejected_records=0,
        warning_count=0,
    )
    versions = {
        "CASE-A": [("1010", "10"), ("1001", "1"), ("1002", "2")],
        "CASE-B": [("2001", "unexpected")],
        "CASE-C": [("3002", "2"), ("3003", "02")],
        "CASE-D": [("4000", "invalid"), ("4003", "3")],
        "CASE-E": [("5001", "1")],
    }
    source_row_number = 2
    for case_id, case_versions in versions.items():
        case_record = FaersCase(case_id=case_id, created_by_run=run)
        session.add(case_record)
        for primary_id, case_version in case_versions:
            session.add(
                FaersReportVersion(
                    primary_id=primary_id,
                    case=case_record,
                    case_version=case_version,
                    source_year=2023,
                    source_quarter=4,
                    source_member=member,
                    ingestion_run=run,
                    source_row_number=source_row_number,
                )
            )
            source_row_number += 1
    session.commit()


def test_selects_unique_highest_numeric_case_version_without_mutation(session: Session) -> None:
    before = session.scalar(select(func.count()).select_from(FaersReportVersion))

    latest = session.scalars(latest_report_versions_statement()).all()

    assert {(item.case_id, item.primary_id, item.case_version) for item in latest} == {
        ("CASE-A", "1010", "10"),
        ("CASE-D", "4003", "3"),
        ("CASE-E", "5001", "1"),
    }
    assert session.scalar(select(func.count()).select_from(FaersReportVersion)) == before == 9
    assert session.get(FaersReportVersion, "1001") is not None
    assert session.get(FaersReportVersion, "1002") is not None


def test_reports_invalid_versions_and_numeric_ties_explicitly(session: Session) -> None:
    rows = session.execute(report_version_resolution_statement()).mappings()
    resolutions = {str(row["case_id"]): row for row in rows}

    assert resolutions["CASE-A"]["resolution_status"] == ReportVersionResolutionStatus.RESOLVED
    assert resolutions["CASE-A"]["maximum_numeric_version"] == 10
    assert resolutions["CASE-A"]["maximum_version_count"] == 1
    assert (
        resolutions["CASE-B"]["resolution_status"] == ReportVersionResolutionStatus.INVALID_VERSION
    )
    assert resolutions["CASE-B"]["maximum_numeric_version"] is None
    assert resolutions["CASE-B"]["maximum_version_count"] == 0
    assert resolutions["CASE-C"]["resolution_status"] == ReportVersionResolutionStatus.VERSION_TIE
    assert resolutions["CASE-C"]["maximum_numeric_version"] == 2
    assert resolutions["CASE-C"]["maximum_version_count"] == 2
    assert resolutions["CASE-D"]["resolution_status"] == ReportVersionResolutionStatus.RESOLVED


def test_latest_statement_is_composable_for_future_analytics(session: Session) -> None:
    statement = latest_report_versions_statement().where(FaersReportVersion.case_id == "CASE-A")

    selected = session.scalars(statement).one()

    assert selected.primary_id == "1010"


def test_statements_compile_for_mysql_8() -> None:
    dialect = mysql.dialect()  # type: ignore[no-untyped-call]
    latest_sql = str(latest_report_versions_statement().compile(dialect=dialect))
    resolution_sql = str(report_version_resolution_statement().compile(dialect=dialect))

    assert "REGEXP" in latest_sql
    assert "OVER (PARTITION BY" in latest_sql
    assert "CAST" in latest_sql
    assert "REGEXP" in resolution_sql
