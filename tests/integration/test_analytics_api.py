"""Guarded live-MySQL smoke tests for the read-only analytics API."""

import os

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from pharmasense.api.dependencies import get_analytics_service
from pharmasense.api.main import app
from pharmasense.api.services.analytics import AnalyticsService
from pharmasense.config.settings import Settings


@pytest.mark.integration
def test_read_only_analytics_endpoints_execute_against_mysql() -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("TEST_DATABASE_URL is not configured")

    service = AnalyticsService(Settings(_env_file=None, database_url=SecretStr(database_url)))
    app.dependency_overrides[get_analytics_service] = lambda: service
    client = TestClient(app)
    try:
        signals = client.get("/api/v1/signals?limit=1&minimum_pair_reports=1")
        drugs = client.get("/api/v1/drugs?limit=1")
        snapshots = client.get("/api/v1/source-snapshots?limit=1")
        historical = client.get(
            "/api/v1/historical/signals/SYNTHETIC-NOT-PRESENT/reactions/SYNTHETIC-NOT-PRESENT",
            params={"start_quarter": "2023Q1", "end_quarter": "2023Q4"},
        )
    finally:
        app.dependency_overrides.clear()

    assert signals.status_code == 200
    assert drugs.status_code == 200
    assert snapshots.status_code == 200
    assert historical.status_code == 200
    assert signals.json()["returned_count"] <= 1
    assert drugs.json()["returned_count"] <= 1
    assert snapshots.json()["returned_count"] <= 1
    assert historical.json()["returned_count"] <= 4
