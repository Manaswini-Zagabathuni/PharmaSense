"""Guarded live-MySQL verification for the synthetic demonstration workflow."""

import os

import pytest
from fastapi.testclient import TestClient

from pharmasense.api.dependencies import get_analytics_service
from pharmasense.api.main import app
from pharmasense.api.services.analytics import AnalyticsService
from pharmasense.config.settings import Settings
from pharmasense.db.engine import build_engine
from pharmasense.demo.seed import DEMO_DRUG_A, DEMO_REACTION_A, seed_demo_data


@pytest.mark.integration
def test_seeded_demo_flows_execute_through_api_and_mysql() -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("TEST_DATABASE_URL is not configured")

    engine = build_engine(database_url)
    try:
        first = seed_demo_data(engine)
        second = seed_demo_data(engine)
        service = AnalyticsService(Settings(_env_file=None), engine=engine)
        app.dependency_overrides[get_analytics_service] = lambda: service
        client = TestClient(app)
        try:
            signals = client.get("/api/v1/signals?limit=25")
            detail = client.get(f"/api/v1/signals/{DEMO_DRUG_A}/reactions/{DEMO_REACTION_A}")
            drugs = client.get("/api/v1/drugs?limit=25&offset=0")
            reactions = client.get(f"/api/v1/drugs/{DEMO_DRUG_A}/reactions?limit=25")
        finally:
            app.dependency_overrides.clear()
    finally:
        engine.dispose()

    assert first.report_count == 20
    assert second.created is False
    assert signals.status_code == 200
    assert any(item["drug_name"] == DEMO_DRUG_A for item in signals.json()["items"])
    assert detail.status_code == 200
    assert detail.json()["signal"]["a"] == 8
    assert drugs.status_code == 200
    assert any(item["drug_name"] == DEMO_DRUG_A for item in drugs.json()["items"])
    assert reactions.status_code == 200
    assert reactions.json()["returned_count"] == 2
