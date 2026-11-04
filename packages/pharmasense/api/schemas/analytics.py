"""Validated public schemas for read-only FAERS analytics endpoints."""

from pydantic import BaseModel, ConfigDict

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


class ErrorResponse(AnalyticsSchema):
    """Sanitized API error body."""

    detail: str
