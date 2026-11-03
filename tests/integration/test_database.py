"""MySQL connectivity integration test."""

import os

import pytest
from sqlalchemy import create_engine, text


@pytest.mark.integration
def test_clean_database_accepts_queries_after_migration() -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("TEST_DATABASE_URL is not configured")

    engine = create_engine(database_url, pool_pre_ping=True)
    with engine.connect() as connection:
        revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()

    assert revision == "20261021_0001"
