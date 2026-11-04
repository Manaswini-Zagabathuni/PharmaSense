"""MySQL connectivity integration test."""

import os

import pytest
from sqlalchemy import create_engine, inspect, text

from pharmasense.analytics.drug_reactions import (
    drug_reaction_summary_statement,
    drug_summary_statement,
    most_reported_reactions_for_drug_statement,
)
from pharmasense.analytics.faers_versions import (
    latest_report_versions_statement,
    report_version_resolution_statement,
)
from pharmasense.analytics.signals import (
    drug_reaction_contingency_statement,
    observed_drug_reaction_contingencies_statement,
)

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


@pytest.mark.integration
def test_latest_report_version_queries_execute_on_mysql() -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("TEST_DATABASE_URL is not configured")

    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            connection.execute(latest_report_versions_statement().limit(1)).all()
            connection.execute(report_version_resolution_statement().limit(1)).all()
    finally:
        engine.dispose()


@pytest.mark.integration
def test_drug_reaction_analytics_queries_execute_on_mysql() -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("TEST_DATABASE_URL is not configured")

    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            connection.execute(drug_summary_statement().limit(1)).all()
            connection.execute(drug_reaction_summary_statement().limit(1)).all()
            connection.execute(
                most_reported_reactions_for_drug_statement("SYNTHETIC-NOT-PRESENT", limit=1)
            ).all()
    finally:
        engine.dispose()


@pytest.mark.integration
def test_signal_contingency_queries_execute_on_mysql() -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("TEST_DATABASE_URL is not configured")

    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            row = connection.execute(
                drug_reaction_contingency_statement(
                    "SYNTHETIC-NOT-PRESENT", "SYNTHETIC-NOT-PRESENT"
                )
            ).one()
            connection.execute(observed_drug_reaction_contingencies_statement().limit(1)).all()
    finally:
        engine.dispose()

    assert row._mapping["population_size"] >= 0
