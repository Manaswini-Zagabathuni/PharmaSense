"""Validated public schemas for read-only FAERS analytics endpoints."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from pharmasense.analytics.historical import HistoricalPopulationSelectionRule
from pharmasense.analytics.prioritization import (
    PriorityExclusionReason,
    SignalEligibilityReason,
)
from pharmasense.analytics.signals import UndefinedMetricReason


class AnalyticsSchema(BaseModel):
    """Strict base schema that supports conversion from typed domain results."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)


class MetricEstimateResponse(AnalyticsSchema):
    """Finite point estimate or explicit undefined reason."""

    value: float | None
    undefined_reason: UndefinedMetricReason | None


class RorConfidenceIntervalResponse(AnalyticsSchema):
    """Two-sided log-ROR interval or explicit undefined reason."""

    confidence_level: float
    lower_bound: float | None
    upper_bound: float | None
    undefined_reason: UndefinedMetricReason | None


class SignalThresholdsResponse(AnalyticsSchema):
    """Thresholds used to evaluate and prioritize a signal."""

    minimum_pair_reports: int
    minimum_population: int | None
    minimum_ror_lower_bound: float


class SignalResponse(AnalyticsSchema):
    """Typed Phase 2D result for one drug-reaction pair."""

    drug_name: str
    reaction_term: str
    analysis_population: int
    a: int
    b: int
    c: int
    d: int
    prr: MetricEstimateResponse
    ror: MetricEstimateResponse
    ror_confidence_interval: RorConfidenceIntervalResponse
    thresholds: SignalThresholdsResponse
    is_observed: bool
    metrics_calculable: bool
    statistically_evaluable: bool
    eligible_for_prioritization: bool
    ineligibility_reasons: tuple[SignalEligibilityReason, ...]
    is_prioritized: bool
    priority_exclusion_reason: PriorityExclusionReason | None


class SignalListResponse(AnalyticsSchema):
    """Bounded prioritized-signal response."""

    items: list[SignalResponse]
    returned_count: int
    limit: int
    research_notice: str


class SignalDetailResponse(AnalyticsSchema):
    """Observed signal detail with interpretation notice."""

    signal: SignalResponse
    research_notice: str


class DrugSummaryResponse(AnalyticsSchema):
    """One source drug-name aggregate."""

    drug_name: str
    report_count: int
    case_count: int


class DrugListResponse(AnalyticsSchema):
    """Bounded deterministic drug-summary page."""

    items: list[DrugSummaryResponse]
    returned_count: int
    limit: int
    offset: int
    research_notice: str


class DrugReactionSummaryResponse(AnalyticsSchema):
    """One report-level drug-reaction co-reporting aggregate."""

    drug_name: str
    reaction_term: str
    report_count: int
    case_count: int


class DrugReactionListResponse(AnalyticsSchema):
    """Bounded reactions for one source drug-name group."""

    drug_name: str
    items: list[DrugReactionSummaryResponse]
    returned_count: int
    limit: int
    research_notice: str


class SourceTermResponse(AnalyticsSchema):
    """One exact source-derived FAERS term, without normalization claims."""

    term: str


class TermDiscoveryResponse(AnalyticsSchema):
    """Bounded deterministic source-term discovery results."""

    items: list[SourceTermResponse]
    returned_count: int
    limit: int
    research_notice: str
    source_term_notice: str


class ErrorResponse(AnalyticsSchema):
    """Sanitized API error body."""

    detail: str


class SourceSnapshotResponse(AnalyticsSchema):
    """Safe archive provenance and completed-ingestion state."""

    source_quarter: str
    source_name: str
    filename: str
    archive_sha256: str
    retrieved_at: datetime
    known_in_provenance: bool
    completed_ingestion_runs: int
    latest_completed_at: datetime | None
    persisted_report_count: int
    successfully_loaded_report_count: int
    successfully_loaded_case_count: int
    contains_successfully_loaded_reports: bool


class SourceSnapshotListResponse(AnalyticsSchema):
    """Bounded deterministic inventory of immutable source archives."""

    items: list[SourceSnapshotResponse]
    returned_count: int
    limit: int


class HistoricalAnalysisMetadataResponse(AnalyticsSchema):
    """Reproducible loaded-source population definition and exclusions."""

    selection_rule: HistoricalPopulationSelectionRule
    requested_start_quarter: str
    requested_end_quarter: str
    selected_source_quarters: tuple[str, ...]
    resolved_report_count: int
    resolved_case_count: int
    excluded_invalid_version_case_count: int
    excluded_version_tie_case_count: int


class QuarterSignalResponse(AnalyticsSchema):
    """One signal result independently resolved within one source quarter."""

    source_quarter: str
    signal: SignalResponse


class HistoricalSignalResponse(AnalyticsSchema):
    """Quarter signal series with an explicit reproducible population boundary."""

    metadata: HistoricalAnalysisMetadataResponse
    items: list[QuarterSignalResponse]
    returned_count: int
    research_notice: str
    historical_method_notice: str
