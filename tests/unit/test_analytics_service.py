"""Analytics application-service tests against a synthetic in-memory database."""

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from pharmasense.analytics.prioritization import SignalThresholds
from pharmasense.api.services.analytics import AnalyticsService
from pharmasense.config.settings import Settings
from pharmasense.db.base import Base
from pharmasense.db.models import FaersDrug, FaersReaction, FaersReportVersion
from tests.unit.analytics.test_signals import seed_signal_population


def test_service_executes_only_read_only_analytics_and_reconciles_results() -> None:
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
