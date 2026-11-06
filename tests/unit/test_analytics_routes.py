"""Read-only analytics API route tests with dependency-isolated services."""

from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from json import dumps

import pytest
from fastapi.testclient import TestClient

from pharmasense.analytics.historical import (
    HistoricalAnalysisMetadata,
    HistoricalPopulationSelectionRule,
    HistoricalSignalResult,
    QuarterSignalResult,
    SourceQuarter,
    SourceSnapshotRecord,
)
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
    snapshots: list[SourceSnapshotRecord] = field(default_factory=list)
    historical_result: HistoricalSignalResult | None = None

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

    def list_source_snapshots(self, *, limit: int) -> list[SourceSnapshotRecord]:
        return self.snapshots[:limit]

    def get_historical_signal(
        self,
        drug_name: str,
        reaction_term: str,
        *,
        start_quarter: SourceQuarter,
        end_quarter: SourceQuarter,
    ) -> HistoricalSignalResult:
        if self.historical_result is None:
            raise AssertionError("historical result was not configured")
        return self.historical_result


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


def test_source_snapshot_inventory_distinguishes_provenance_from_loaded_reports() -> None:
    service = StubAnalyticsService(
        snapshots=[
            SourceSnapshotRecord(
                source_quarter=SourceQuarter(2023, 4),
                source_name="FDA FAERS",
                filename="faers_ascii_2023Q4.zip",
                archive_sha256="a" * 64,
                retrieved_at=datetime(2026, 11, 1, tzinfo=UTC),
                completed_ingestion_runs=0,
                latest_completed_at=None,
                persisted_report_count=10,
                successfully_loaded_report_count=0,
                successfully_loaded_case_count=0,
            )
        ]
    )

    response = _client_with(service).get("/api/v1/source-snapshots?limit=1")

    assert response.status_code == 200
    body = response.json()
    assert body["returned_count"] == 1
    assert body["items"][0]["source_quarter"] == "2023Q4"
    assert body["items"][0]["known_in_provenance"] is True
    assert body["items"][0]["contains_successfully_loaded_reports"] is False
    assert "storage_path" not in dumps(body)
    assert "source_url" not in dumps(body)


@pytest.mark.parametrize("limit", [0, 201])
def test_source_snapshot_inventory_limit_is_validated(limit: int) -> None:
    response = _client_with(StubAnalyticsService()).get(
        "/api/v1/source-snapshots", params={"limit": limit}
    )

    assert response.status_code == 422


def test_historical_signal_returns_population_metadata_and_research_notices() -> None:
    quarter = SourceQuarter(2023, 4)
    signal = _signal()
    service = StubAnalyticsService(
        historical_result=HistoricalSignalResult(
            metadata=HistoricalAnalysisMetadata(
                selection_rule=(
                    HistoricalPopulationSelectionRule.COMPLETED_INGESTIONS_IN_INCLUSIVE_QUARTER_RANGE
                ),
                requested_start_quarter=quarter,
                requested_end_quarter=quarter,
                selected_source_quarters=(quarter,),
                resolved_report_count=1000,
                resolved_case_count=1000,
                excluded_invalid_version_case_count=2,
                excluded_version_tie_case_count=1,
            ),
            quarters=(QuarterSignalResult(quarter, signal),),
        )
    )

    response = _client_with(service).get(
        "/api/v1/historical/signals/SYNTHETIC%20DRUG/reactions/SYNTHETIC%20EVENT",
        params={"start_quarter": "2023Q4", "end_quarter": "2023Q4"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["metadata"]["selected_source_quarters"] == ["2023Q4"]
    assert body["metadata"]["excluded_invalid_version_case_count"] == 2
    assert body["items"][0]["signal"]["a"] == 20
    assert "not a retrospective as-of" in body["historical_method_notice"]
    assert "causality" in body["research_notice"]


@pytest.mark.parametrize(
    ("start", "end"),
    [
        ("2023-Q1", "2023Q2"),
        ("2023Q1", "2023Q5"),
        ("2023Q4", "2023Q1"),
        ("2000Q1", "2021Q1"),
    ],
)
def test_historical_signal_rejects_malformed_reversed_or_unbounded_ranges(
    start: str, end: str
) -> None:
    response = _client_with(StubAnalyticsService()).get(
        "/api/v1/historical/signals/DRUG/reactions/EVENT",
        params={"start_quarter": start, "end_quarter": end},
    )

    assert response.status_code == 422


def test_historical_database_errors_are_sanitized() -> None:
    class FailingHistoricalService(StubAnalyticsService):
        def get_historical_signal(
            self,
            drug_name: str,
            reaction_term: str,
            *,
            start_quarter: SourceQuarter,
            end_quarter: SourceQuarter,
        ) -> HistoricalSignalResult:
            raise AnalyticsExecutionError("mysql://user:secret@example.invalid/database")

    response = _client_with(FailingHistoricalService()).get(
        "/api/v1/historical/signals/DRUG/reactions/EVENT",
        params={"start_quarter": "2023Q1", "end_quarter": "2023Q2"},
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "Analytics request could not be completed."}
    assert "secret" not in response.text
