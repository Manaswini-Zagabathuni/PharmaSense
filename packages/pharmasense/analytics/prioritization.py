"""Transparent confidence analytics and prioritization for FAERS reporting signals."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from heapq import nsmallest
from math import exp, isfinite, log, sqrt
from statistics import NormalDist

from sqlalchemy import select
from sqlalchemy.sql import Select

from pharmasense.analytics.signals import (
    ContingencyTable,
    MetricEstimate,
    UndefinedMetricReason,
    calculate_disproportionality,
    observed_drug_reaction_contingencies_statement,
)


class SignalEligibilityReason(StrEnum):
    """Stable reasons that an observed pair is not statistically eligible."""

    PAIR_NOT_OBSERVED = "PAIR_NOT_OBSERVED"
    BELOW_MINIMUM_PAIR_REPORTS = "BELOW_MINIMUM_PAIR_REPORTS"
    BELOW_MINIMUM_POPULATION = "BELOW_MINIMUM_POPULATION"
    PRR_UNDEFINED = "PRR_UNDEFINED"
    ROR_UNDEFINED = "ROR_UNDEFINED"
    ROR_CONFIDENCE_INTERVAL_UNDEFINED = "ROR_CONFIDENCE_INTERVAL_UNDEFINED"


class PriorityExclusionReason(StrEnum):
    """Stable reasons that a result is not included in the priority ranking."""

    NOT_ELIGIBLE = "NOT_ELIGIBLE"
    LOWER_CONFIDENCE_BOUND_NOT_ABOVE_MINIMUM = "LOWER_CONFIDENCE_BOUND_NOT_ABOVE_MINIMUM"


@dataclass(frozen=True)
class SignalThresholds:
    """Validated transparent thresholds applied before and after estimation."""

    minimum_pair_reports: int = 3
    minimum_population: int | None = None
    minimum_ror_lower_bound: float = 1.0

    def __post_init__(self) -> None:
        if type(self.minimum_pair_reports) is not int or self.minimum_pair_reports < 1:
            raise ValueError("minimum_pair_reports must be a positive integer")
        if self.minimum_population is not None and (
            type(self.minimum_population) is not int or self.minimum_population < 1
        ):
            raise ValueError("minimum_population must be a positive integer or None")
        if (
            isinstance(self.minimum_ror_lower_bound, bool)
            or not isinstance(self.minimum_ror_lower_bound, int | float)
            or not isfinite(self.minimum_ror_lower_bound)
            or self.minimum_ror_lower_bound < 0
        ):
            raise ValueError("minimum_ror_lower_bound must be a finite non-negative number")


@dataclass(frozen=True)
class RorConfidenceInterval:
    """A finite two-sided log-ROR interval or an explicit undefined reason."""

    confidence_level: float
    lower_bound: float | None
    upper_bound: float | None
    undefined_reason: UndefinedMetricReason | None

    @property
    def is_defined(self) -> bool:
        """Return whether finite lower and upper bounds are available."""

        return self.lower_bound is not None and self.upper_bound is not None


@dataclass(frozen=True)
class SignalResult:
    """Typed evidence and status for one reported drug-reaction pair."""

    drug_name: str
    reaction_term: str
    analysis_population: int
    a: int
    b: int
    c: int
    d: int
    prr: MetricEstimate
    ror: MetricEstimate
    ror_confidence_interval: RorConfidenceInterval
    thresholds: SignalThresholds
    is_observed: bool
    metrics_calculable: bool
    statistically_evaluable: bool
    eligible_for_prioritization: bool
    ineligibility_reasons: tuple[SignalEligibilityReason, ...]
    is_prioritized: bool
    priority_exclusion_reason: PriorityExclusionReason | None


def _validate_confidence_level(confidence_level: float) -> None:
    if (
        isinstance(confidence_level, bool)
        or not isinstance(confidence_level, int | float)
        or not isfinite(confidence_level)
        or not 0 < confidence_level < 1
    ):
        raise ValueError("confidence_level must be a finite number strictly between 0 and 1")


def calculate_ror_confidence_interval(
    table: ContingencyTable, *, confidence_level: float = 0.95
) -> RorConfidenceInterval:
    """Calculate an uncorrected two-sided normal interval on the log-ROR scale."""

    _validate_confidence_level(confidence_level)
    normalized_level = float(confidence_level)
    if table.population_size == 0:
        return RorConfidenceInterval(
            normalized_level,
            lower_bound=None,
            upper_bound=None,
            undefined_reason=UndefinedMetricReason.EMPTY_POPULATION,
        )
    if 0 in (table.a, table.b, table.c, table.d):
        return RorConfidenceInterval(
            normalized_level,
            lower_bound=None,
            upper_bound=None,
            undefined_reason=UndefinedMetricReason.ZERO_CELL_CONFIDENCE_INTERVAL,
        )

    log_ror = log(table.a) + log(table.d) - log(table.b) - log(table.c)
    standard_error = sqrt(1 / table.a + 1 / table.b + 1 / table.c + 1 / table.d)
    critical_value = NormalDist().inv_cdf(0.5 + normalized_level / 2)
    try:
        lower_bound = exp(log_ror - critical_value * standard_error)
        upper_bound = exp(log_ror + critical_value * standard_error)
    except OverflowError:
        lower_bound = float("inf")
        upper_bound = float("inf")
    if not isfinite(lower_bound) or not isfinite(upper_bound):
        return RorConfidenceInterval(
            normalized_level,
            lower_bound=None,
            upper_bound=None,
            undefined_reason=UndefinedMetricReason.NON_FINITE_RESULT,
        )
    return RorConfidenceInterval(
        normalized_level,
        lower_bound=lower_bound,
        upper_bound=upper_bound,
        undefined_reason=None,
    )


def evaluate_signal(
    drug_name: str,
    reaction_term: str,
    table: ContingencyTable,
    *,
    thresholds: SignalThresholds | None = None,
    confidence_level: float = 0.95,
) -> SignalResult:
    """Evaluate one pair without turning a reporting association into a causal claim."""

    applied_thresholds = thresholds or SignalThresholds()
    metrics = calculate_disproportionality(table)
    interval = calculate_ror_confidence_interval(table, confidence_level=confidence_level)
    reasons: list[SignalEligibilityReason] = []
    if table.a == 0:
        reasons.append(SignalEligibilityReason.PAIR_NOT_OBSERVED)
    if table.a < applied_thresholds.minimum_pair_reports:
        reasons.append(SignalEligibilityReason.BELOW_MINIMUM_PAIR_REPORTS)
    if (
        applied_thresholds.minimum_population is not None
        and table.population_size < applied_thresholds.minimum_population
    ):
        reasons.append(SignalEligibilityReason.BELOW_MINIMUM_POPULATION)
    if not metrics.prr.is_defined:
        reasons.append(SignalEligibilityReason.PRR_UNDEFINED)
    if not metrics.ror.is_defined:
        reasons.append(SignalEligibilityReason.ROR_UNDEFINED)
    if not interval.is_defined:
        reasons.append(SignalEligibilityReason.ROR_CONFIDENCE_INTERVAL_UNDEFINED)

    metrics_calculable = metrics.prr.is_defined and metrics.ror.is_defined
    statistically_evaluable = metrics_calculable and interval.is_defined
    eligible = not reasons
    lower_bound = interval.lower_bound
    is_prioritized = (
        eligible
        and lower_bound is not None
        and lower_bound > applied_thresholds.minimum_ror_lower_bound
    )
    if not eligible:
        priority_exclusion_reason = PriorityExclusionReason.NOT_ELIGIBLE
    elif not is_prioritized:
        priority_exclusion_reason = PriorityExclusionReason.LOWER_CONFIDENCE_BOUND_NOT_ABOVE_MINIMUM
    else:
        priority_exclusion_reason = None

    return SignalResult(
        drug_name=drug_name,
        reaction_term=reaction_term,
        analysis_population=table.population_size,
        a=table.a,
        b=table.b,
        c=table.c,
        d=table.d,
        prr=metrics.prr,
        ror=metrics.ror,
        ror_confidence_interval=interval,
        thresholds=applied_thresholds,
        is_observed=table.a > 0,
        metrics_calculable=metrics_calculable,
        statistically_evaluable=statistically_evaluable,
        eligible_for_prioritization=eligible,
        ineligibility_reasons=tuple(reasons),
        is_prioritized=is_prioritized,
        priority_exclusion_reason=priority_exclusion_reason,
    )


def signal_candidate_contingencies_statement(
    thresholds: SignalThresholds | None = None,
) -> Select[tuple[str, str, int, int, int, int, int]]:
    """Filter Phase 2C observed-pair aggregates by database-applicable thresholds."""

    applied_thresholds = thresholds or SignalThresholds()
    contingencies = observed_drug_reaction_contingencies_statement().subquery(
        "observed_signal_contingencies"
    )
    statement = select(contingencies).where(
        contingencies.c.a >= applied_thresholds.minimum_pair_reports
    )
    if applied_thresholds.minimum_population is not None:
        statement = statement.where(
            contingencies.c.population_size >= applied_thresholds.minimum_population
        )
    return statement.order_by(
        contingencies.c.a.desc(), contingencies.c.drug_name, contingencies.c.reaction_term
    )


def rank_prioritized_signals(
    results: Iterable[SignalResult], *, limit: int | None = None
) -> list[SignalResult]:
    """Rank qualifying signals with deterministic tie-breaks and optional bounded memory."""

    if limit is not None and (type(limit) is not int or limit < 1):
        raise ValueError("limit must be a positive integer or None")
    prioritized = (result for result in results if result.is_prioritized)
    if limit is not None:
        return nsmallest(limit, prioritized, key=_priority_key)
    return sorted(prioritized, key=_priority_key)


def _priority_key(result: SignalResult) -> tuple[float, int, float, float, str, str]:
    return (
        -_defined_value(result.ror_confidence_interval.lower_bound),
        -result.a,
        -_defined_value(result.ror.value),
        -_defined_value(result.prr.value),
        result.drug_name,
        result.reaction_term,
    )


def _defined_value(value: float | None) -> float:
    """Narrow values guaranteed by the prioritized-result invariant."""

    if value is None:
        raise ValueError("prioritized signals must contain defined finite estimates")
    return value
