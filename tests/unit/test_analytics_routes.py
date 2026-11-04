"""Read-only analytics API route tests with dependency-isolated services."""

from collections.abc import Iterator
from dataclasses import dataclass, field
from json import dumps

import pytest
from fastapi.testclient import TestClient

from pharmasense.analytics.prioritization import (
    SignalResult,
    SignalThresholds,
    evaluate_signal,
)
from pharmasense.analytics.signals import ContingencyTable
from pharmasense.api.dependencies import get_analytics_service
from pharmasense.api.errors import AnalyticsExecutionError
from pharmasense.api.main import app
from pharmasense.api.services.analytics import (
    AnalyticsService,
    DrugReactionSummaryRecord,
    DrugSummaryRecord,
)
from pharmasense.config.settings import Settings


@dataclass
class StubAnalyticsService:
    """Record route orchestration without executing database code."""

    signal_items: list[SignalResult] = field(default_factory=list)
    signal_details: dict[tuple[str, str], SignalResult] = field(default_factory=dict)
    drugs: list[DrugSummaryRecord] = field(default_factory=list)
    reactions: dict[str, list[DrugReactionSummaryRecord] | None] = field(default_factory=dict)
    signal_calls: list[tuple[int, SignalThresholds]] = field(default_factory=list)

    def list_prioritized_signals(
        self, *, limit: int, thresholds: SignalThresholds
    ) -> list[SignalResult]:
        self.signal_calls.append((limit, thresholds))
        return self.signal_items[:limit]

    def get_signal(
        self,
        drug_name: str,
        reaction_term: str,
        *,
        thresholds: SignalThresholds | None = None,
    ) -> SignalResult | None:
        return self.signal_details.get((drug_name, reaction_term))

    def list_drugs(self, *, limit: int, offset: int) -> list[DrugSummaryRecord]:
        return self.drugs[offset : offset + limit]

    def list_drug_reactions(
        self, drug_name: str, *, limit: int
    ) -> list[DrugReactionSummaryRecord] | None:
        records = self.reactions.get(drug_name)
        return None if records is None else records[:limit]


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> Iterator[None]:
    yield
    app.dependency_overrides.clear()


def _signal(
    drug_name: str = "SYNTHETIC DRUG",
    reaction_term: str = "SYNTHETIC EVENT",
    *,
    table: ContingencyTable | None = None,
    thresholds: SignalThresholds | None = None,
) -> SignalResult:
    return evaluate_signal(
        drug_name,
        reaction_term,
        table or ContingencyTable(a=20, b=80, c=10, d=890),
        thresholds=thresholds,
    )


def _client_with(service: object) -> TestClient:
    app.dependency_overrides[get_analytics_service] = lambda: service
    return TestClient(app)


def test_prioritized_signals_apply_validated_limit_and_thresholds() -> None:
    thresholds = SignalThresholds(
        minimum_pair_reports=5,
        minimum_population=100,
        minimum_ror_lower_bound=1.5,
    )
    service = StubAnalyticsService(signal_items=[_signal(thresholds=thresholds)])

    response = _client_with(service).get(
        "/api/v1/signals",
        params={
            "limit": 2,
            "minimum_pair_reports": 5,
            "minimum_population": 100,
            "minimum_ror_lower_bound": 1.5,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["returned_count"] == 1
    assert body["items"][0]["a"] == 20
    assert body["items"][0]["prr"]["value"] == pytest.approx(18.0)
    assert body["items"][0]["ror_confidence_interval"]["lower_bound"] > 1.5
    assert service.signal_calls == [(2, thresholds)]
    serialized = dumps(body).lower()
    assert "password" not in serialized
    assert "database_url" not in serialized


@pytest.mark.parametrize(
    "query",
    [
        "limit=0",
        "limit=101",
        "minimum_pair_reports=0",
        "minimum_population=0",
        "minimum_ror_lower_bound=-1",
        "minimum_ror_lower_bound=1000001",
    ],
)
def test_signal_query_validation_rejects_unsafe_values(query: str) -> None:
    response = _client_with(StubAnalyticsService()).get(f"/api/v1/signals?{query}")

    assert response.status_code == 422


def test_prioritized_signals_return_clear_empty_collection() -> None:
    response = _client_with(StubAnalyticsService()).get("/api/v1/signals")

    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["returned_count"] == 0


def test_signal_detail_distinguishes_eligible_and_ineligible_observed_pairs() -> None:
    eligible = _signal()
    ineligible = _signal(
        "SMALL DRUG",
        "SMALL EVENT",
        table=ContingencyTable(a=1, b=2, c=1, d=20),
    )
    service = StubAnalyticsService(
        signal_details={
            (eligible.drug_name, eligible.reaction_term): eligible,
            (ineligible.drug_name, ineligible.reaction_term): ineligible,
        }
    )
    client = _client_with(service)

    eligible_response = client.get("/api/v1/signals/SYNTHETIC%20DRUG/reactions/SYNTHETIC%20EVENT")
    ineligible_response = client.get("/api/v1/signals/SMALL%20DRUG/reactions/SMALL%20EVENT")

    assert eligible_response.status_code == 200
    assert eligible_response.json()["signal"]["is_prioritized"] is True
    assert ineligible_response.status_code == 200
    assert ineligible_response.json()["signal"]["is_observed"] is True
    assert ineligible_response.json()["signal"]["eligible_for_prioritization"] is False
    assert (
        "BELOW_MINIMUM_PAIR_REPORTS"
        in ineligible_response.json()["signal"]["ineligibility_reasons"]
    )


def test_missing_signal_pair_returns_404() -> None:
    response = _client_with(StubAnalyticsService()).get("/api/v1/signals/MISSING/reactions/MISSING")

    assert response.status_code == 404
    assert "not observed" in response.json()["detail"]


def test_drug_summary_pagination_is_bounded_and_deterministic() -> None:
    service = StubAnalyticsService(
        drugs=[
            DrugSummaryRecord("A", 10, 10),
            DrugSummaryRecord("B", 5, 5),
            DrugSummaryRecord("C", 1, 1),
        ]
    )

    response = _client_with(service).get("/api/v1/drugs?limit=1&offset=1")

    assert response.status_code == 200
    assert response.json()["items"] == [{"drug_name": "B", "report_count": 5, "case_count": 5}]
    assert response.json()["offset"] == 1


@pytest.mark.parametrize("query", ["limit=0", "limit=201", "offset=-1", "offset=1000001"])
def test_drug_summary_validation_rejects_unsafe_pagination(query: str) -> None:
    response = _client_with(StubAnalyticsService()).get(f"/api/v1/drugs?{query}")

    assert response.status_code == 422


def test_drug_reactions_return_results_and_missing_drug_returns_404() -> None:
    service = StubAnalyticsService(
        reactions={
            "KNOWN": [DrugReactionSummaryRecord("KNOWN", "EVENT", 7, 7)],
            "NO EVENTS": [],
        }
    )
    client = _client_with(service)

    response = client.get("/api/v1/drugs/KNOWN/reactions?limit=1")
    empty_response = client.get("/api/v1/drugs/NO%20EVENTS/reactions")
    missing_response = client.get("/api/v1/drugs/MISSING/reactions")

    assert response.status_code == 200
    assert response.json()["items"][0]["reaction_term"] == "EVENT"
    assert empty_response.status_code == 200
    assert empty_response.json()["items"] == []
    assert missing_response.status_code == 404


@pytest.mark.parametrize("limit", [0, 101])
def test_drug_reaction_limit_is_validated(limit: int) -> None:
    response = _client_with(StubAnalyticsService()).get(
        "/api/v1/drugs/KNOWN/reactions", params={"limit": limit}
    )

    assert response.status_code == 422


def test_unavailable_database_and_internal_errors_are_sanitized() -> None:
    unavailable = _client_with(AnalyticsService(Settings(_env_file=None))).get("/api/v1/drugs")

    class FailingService(StubAnalyticsService):
        def list_drugs(self, *, limit: int, offset: int) -> list[DrugSummaryRecord]:
            raise AnalyticsExecutionError("mysql://user:secret@example.invalid/database")

    failure = _client_with(FailingService()).get("/api/v1/drugs")

    assert unavailable.status_code == 503
    assert unavailable.json() == {"detail": "Analytics database is unavailable."}
    assert failure.status_code == 500
    assert failure.json() == {"detail": "Analytics request could not be completed."}
    assert "secret" not in failure.text
