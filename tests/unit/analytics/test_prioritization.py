"""Confidence analytics and transparent signal-prioritization tests."""

import pytest

from pharmasense.analytics.prioritization import (
    PriorityExclusionReason,
    SignalEligibilityReason,
    SignalThresholds,
    calculate_ror_confidence_interval,
    evaluate_signal,
    rank_prioritized_signals,
)
from pharmasense.analytics.signals import ContingencyTable, UndefinedMetricReason


def test_expected_uncorrected_log_ror_confidence_interval() -> None:
    table = ContingencyTable(a=20, b=80, c=10, d=890)

    interval = calculate_ror_confidence_interval(table)

    assert interval.confidence_level == 0.95
    assert interval.lower_bound == pytest.approx(10.069675398999312)
    assert interval.upper_bound == pytest.approx(49.16369995890811)
    assert interval.undefined_reason is None
    assert interval.is_defined


def test_confidence_interval_is_undefined_for_zero_cells_and_empty_population() -> None:
    zero_cell = calculate_ror_confidence_interval(ContingencyTable(a=1, b=2, c=0, d=3))
    empty = calculate_ror_confidence_interval(ContingencyTable(a=0, b=0, c=0, d=0))

    assert zero_cell.lower_bound is None
    assert zero_cell.upper_bound is None
    assert zero_cell.undefined_reason == UndefinedMetricReason.ZERO_CELL_CONFIDENCE_INTERVAL
    assert empty.undefined_reason == UndefinedMetricReason.EMPTY_POPULATION


@pytest.mark.parametrize("confidence_level", [0.0, 1.0, -0.1, float("inf"), float("nan"), True])
def test_invalid_confidence_levels_are_rejected(confidence_level: float) -> None:
    with pytest.raises(ValueError, match="strictly between"):
        calculate_ror_confidence_interval(
            ContingencyTable(a=1, b=1, c=1, d=1),
            confidence_level=confidence_level,
        )


@pytest.mark.parametrize(
    ("keyword", "value"),
    [
        ("minimum_pair_reports", 0),
        ("minimum_pair_reports", True),
        ("minimum_population", 0),
        ("minimum_ror_lower_bound", -1.0),
        ("minimum_ror_lower_bound", float("inf")),
    ],
)
def test_invalid_thresholds_are_rejected(keyword: str, value: object) -> None:
    with pytest.raises(ValueError):
        SignalThresholds(**{keyword: value})  # type: ignore[arg-type]


def test_positive_table_is_evaluable_eligible_and_prioritized() -> None:
    result = evaluate_signal(
        "SYNTHETIC DRUG",
        "SYNTHETIC EVENT",
        ContingencyTable(a=20, b=80, c=10, d=890),
    )

    assert result.analysis_population == 1000
    assert (result.a, result.b, result.c, result.d) == (20, 80, 10, 890)
    assert result.is_observed
    assert result.metrics_calculable
    assert result.statistically_evaluable
    assert result.eligible_for_prioritization
    assert result.ineligibility_reasons == ()
    assert result.is_prioritized
    assert result.priority_exclusion_reason is None


def test_minimum_pair_and_population_thresholds_are_explicit() -> None:
    result = evaluate_signal(
        "SYNTHETIC DRUG",
        "SYNTHETIC EVENT",
        ContingencyTable(a=2, b=8, c=5, d=85),
        thresholds=SignalThresholds(minimum_pair_reports=3, minimum_population=101),
    )

    assert not result.eligible_for_prioritization
    assert result.ineligibility_reasons == (
        SignalEligibilityReason.BELOW_MINIMUM_PAIR_REPORTS,
        SignalEligibilityReason.BELOW_MINIMUM_POPULATION,
    )
    assert result.priority_exclusion_reason == PriorityExclusionReason.NOT_ELIGIBLE


def test_observed_calculable_pair_can_be_eligible_but_not_prioritized() -> None:
    result = evaluate_signal(
        "SYNTHETIC DRUG",
        "SYNTHETIC EVENT",
        ContingencyTable(a=10, b=10, c=10, d=10),
    )

    assert result.eligible_for_prioritization
    assert not result.is_prioritized
    assert (
        result.priority_exclusion_reason
        == PriorityExclusionReason.LOWER_CONFIDENCE_BOUND_NOT_ABOVE_MINIMUM
    )


def test_unobserved_and_undefined_pair_has_explicit_status_reasons() -> None:
    result = evaluate_signal(
        "SYNTHETIC DRUG",
        "SYNTHETIC EVENT",
        ContingencyTable(a=0, b=2, c=1, d=2),
        thresholds=SignalThresholds(minimum_pair_reports=1),
    )

    assert not result.is_observed
    assert result.metrics_calculable
    assert not result.statistically_evaluable
    assert not result.eligible_for_prioritization
    assert result.ineligibility_reasons == (
        SignalEligibilityReason.PAIR_NOT_OBSERVED,
        SignalEligibilityReason.BELOW_MINIMUM_PAIR_REPORTS,
        SignalEligibilityReason.ROR_CONFIDENCE_INTERVAL_UNDEFINED,
    )


def test_ranking_uses_lower_bound_then_counts_metrics_and_lexical_ties() -> None:
    common = ContingencyTable(a=20, b=80, c=10, d=890)
    results = [
        evaluate_signal("B DRUG", "A EVENT", common),
        evaluate_signal("A DRUG", "Z EVENT", common),
        evaluate_signal(
            "STRONG DRUG",
            "EVENT",
            ContingencyTable(a=30, b=70, c=10, d=890),
        ),
        evaluate_signal(
            "NOT PRIORITIZED",
            "EVENT",
            ContingencyTable(a=10, b=10, c=10, d=10),
        ),
    ]

    ranked = rank_prioritized_signals(reversed(results))

    assert [(result.drug_name, result.reaction_term) for result in ranked] == [
        ("STRONG DRUG", "EVENT"),
        ("A DRUG", "Z EVENT"),
        ("B DRUG", "A EVENT"),
    ]
