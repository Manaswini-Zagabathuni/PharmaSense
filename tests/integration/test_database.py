"""MySQL connectivity integration test."""

import os

import pytest
from sqlalchemy import create_engine, inspect, text

EXPECTED_PHASE_1C_TABLES = {
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


@pytest.mark.integration
def test_clean_database_accepts_queries_after_migration() -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("TEST_DATABASE_URL is not configured")

    engine = create_engine(database_url, pool_pre_ping=True)
    with engine.connect() as connection:
        revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()

    assert revision == "20261103_0002"
    assert set(inspect(engine).get_table_names()) >= EXPECTED_PHASE_1C_TABLES
