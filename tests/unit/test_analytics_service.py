"""Analytics application-service tests against a synthetic in-memory database."""

import json
import logging
from typing import cast

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from pharmasense.analytics.prioritization import SignalThresholds
from pharmasense.api.errors import AnalyticsUnavailableError
from pharmasense.api.services.analytics import AnalyticsService
from pharmasense.config.settings import Settings
from pharmasense.db.base import Base
from pharmasense.db.models import FaersDrug, FaersReaction, FaersReportVersion
from tests.unit.analytics.test_signals import seed_signal_population


def test_service_executes_only_read_only_analytics_and_reconciles_results(
    caplog: pytest.LogCaptureFixture,
) -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_signal_population(session)
        before = (
            session.scalar(select(func.count()).select_from(FaersReportVersion)),
            session.scalar(select(func.count()).select_from(FaersDrug)),
            session.scalar(select(func.count()).select_from(FaersReaction)),
        )

    service = AnalyticsService(Settings(_env_file=None), engine=engine)
    thresholds = SignalThresholds(minimum_pair_reports=1, minimum_ror_lower_bound=0)
    caplog.set_level(logging.INFO, logger="pharmasense.api.services.analytics")

    signals = service.list_prioritized_signals(limit=2, thresholds=thresholds)
    detail = service.get_signal("TARGET", "EVENT", thresholds=thresholds)
    missing = service.get_signal("MISSING", "MISSING", thresholds=thresholds)
    drugs = service.list_drugs(limit=2, offset=0)
    reactions = service.list_drug_reactions("TARGET", limit=2)
    missing_drug = service.list_drug_reactions("MISSING", limit=2)

    with Session(engine) as session:
        after = (
            session.scalar(select(func.count()).select_from(FaersReportVersion)),
            session.scalar(select(func.count()).select_from(FaersDrug)),
            session.scalar(select(func.count()).select_from(FaersReaction)),
        )
    engine.dispose()

    assert signals
    assert detail is not None
    assert detail.a == 1
    assert missing is None
    assert [record.drug_name for record in drugs] == ["OTHER", "TARGET"]
    assert reactions is not None
    assert [record.reaction_term for record in reactions] == ["OTHER EVENT", "EVENT"]
    assert missing_drug is None
    assert after == before

    events: list[dict[str, object]] = [
        cast(dict[str, object], json.loads(record.message))
        for record in caplog.records
        if record.name == "pharmasense.api.services.analytics"
        and json.loads(record.message).get("event") == "analytics_operation_completed"
    ]
    assert {event["operation"] for event in events} == {
        "signal_list_retrieval",
        "signal_detail_retrieval",
        "drug_list_retrieval",
        "drug_reaction_retrieval",
    }
    assert all(event["outcome"] == "success" for event in events)
    durations = [event["duration_ms"] for event in events]
    assert all(isinstance(duration, int | float) and duration >= 0 for duration in durations)
    assert all("TARGET" not in json.dumps(event) for event in events)


def test_failed_analytics_operation_logs_only_stable_timing_fields(
    caplog: pytest.LogCaptureFixture,
) -> None:
    service = AnalyticsService(Settings(_env_file=None))
    caplog.set_level(logging.INFO, logger="pharmasense.api.services.analytics")

    with pytest.raises(AnalyticsUnavailableError):
        service.list_drugs(limit=1, offset=0)

    event = cast(
        dict[str, object],
        json.loads(
            next(
                record.message
                for record in caplog.records
                if record.name == "pharmasense.api.services.analytics"
            )
        ),
    )
    assert event["event"] == "analytics_operation_completed"
    assert event["operation"] == "drug_list_retrieval"
    assert event["outcome"] == "error"
    assert set(event) == {"event", "operation", "outcome", "duration_ms"}
