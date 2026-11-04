"""Read-only FAERS contingency queries and disproportionality calculations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

from sqlalchemy import case, func, literal, select
from sqlalchemy.sql import Select
from sqlalchemy.sql.elements import ColumnElement

from pharmasense.analytics.drug_reactions import (
    drug_reaction_report_presence_cte,
    drug_report_presence_cte,
    reaction_report_presence_cte,
    resolved_latest_report_keys_cte,
)


class UndefinedMetricReason(StrEnum):
    """Stable reasons that a disproportionality estimate is not defined."""

    EMPTY_POPULATION = "EMPTY_POPULATION"
    NO_DRUG_REPORTS = "NO_DRUG_REPORTS"
    NO_NON_DRUG_REPORTS = "NO_NON_DRUG_REPORTS"
    ZERO_COMPARATOR_REACTION_COUNT = "ZERO_COMPARATOR_REACTION_COUNT"
    ZERO_DRUG_NON_REACTION_COUNT = "ZERO_DRUG_NON_REACTION_COUNT"
    ZERO_NON_DRUG_REACTION_COUNT = "ZERO_NON_DRUG_REACTION_COUNT"
    ZERO_CELL_CONFIDENCE_INTERVAL = "ZERO_CELL_CONFIDENCE_INTERVAL"
    NON_FINITE_RESULT = "NON_FINITE_RESULT"


@dataclass(frozen=True)
class ContingencyTable:
    """Validated report-level 2x2 counts for one drug-reaction pair."""

    a: int
    b: int
    c: int
    d: int

    def __post_init__(self) -> None:
        for name, value in (("a", self.a), ("b", self.b), ("c", self.c), ("d", self.d)):
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")

    @property
    def population_size(self) -> int:
        """Return the total number of classified reports."""

        return self.a + self.b + self.c + self.d

    @classmethod
    def from_margins(
        cls,
        *,
        population_size: int,
        drug_report_count: int,
        reaction_report_count: int,
        pair_report_count: int,
    ) -> ContingencyTable:
        """Build a table from database margins, rejecting impossible relationships."""

        counts = {
            "population_size": population_size,
            "drug_report_count": drug_report_count,
            "reaction_report_count": reaction_report_count,
            "pair_report_count": pair_report_count,
        }
        for name, value in counts.items():
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if drug_report_count > population_size or reaction_report_count > population_size:
            raise ValueError("marginal report counts cannot exceed the analysis population")
        if pair_report_count > min(drug_report_count, reaction_report_count):
            raise ValueError("pair report count cannot exceed either marginal count")

        return cls(
            a=pair_report_count,
            b=drug_report_count - pair_report_count,
            c=reaction_report_count - pair_report_count,
            d=population_size - drug_report_count - reaction_report_count + pair_report_count,
        )


@dataclass(frozen=True)
class MetricEstimate:
    """One finite estimate or an explicit reason that it is undefined."""

    value: float | None
    undefined_reason: UndefinedMetricReason | None

    @property
    def is_defined(self) -> bool:
        """Return whether a finite estimate is available."""

        return self.value is not None


@dataclass(frozen=True)
class DisproportionalityMetrics:
    """PRR and ROR estimates for a validated contingency table."""

    contingency: ContingencyTable
    prr: MetricEstimate
    ror: MetricEstimate


def _finite_estimate(value: float) -> MetricEstimate:
    if not isfinite(value):
        return MetricEstimate(None, UndefinedMetricReason.NON_FINITE_RESULT)
    return MetricEstimate(value, None)


def calculate_disproportionality(table: ContingencyTable) -> DisproportionalityMetrics:
    """Calculate uncorrected PRR and ROR without returning infinite values."""

    if table.population_size == 0:
        undefined = MetricEstimate(None, UndefinedMetricReason.EMPTY_POPULATION)
        return DisproportionalityMetrics(table, prr=undefined, ror=undefined)

    drug_reports = table.a + table.b
    non_drug_reports = table.c + table.d
    if drug_reports == 0:
        prr = MetricEstimate(None, UndefinedMetricReason.NO_DRUG_REPORTS)
    elif non_drug_reports == 0:
        prr = MetricEstimate(None, UndefinedMetricReason.NO_NON_DRUG_REPORTS)
    elif table.c == 0:
        prr = MetricEstimate(None, UndefinedMetricReason.ZERO_COMPARATOR_REACTION_COUNT)
    else:
        prr = _finite_estimate((table.a / drug_reports) / (table.c / non_drug_reports))

    if table.b == 0:
        ror = MetricEstimate(None, UndefinedMetricReason.ZERO_DRUG_NON_REACTION_COUNT)
    elif table.c == 0:
        ror = MetricEstimate(None, UndefinedMetricReason.ZERO_NON_DRUG_REACTION_COUNT)
    else:
        ror = _finite_estimate((table.a / table.b) * (table.d / table.c))

    return DisproportionalityMetrics(table, prr=prr, ror=ror)


def drug_reaction_contingency_statement(
    drug_name: str, reaction_term: str
) -> Select[tuple[str, str, int, int, int, int, int]]:
    """Aggregate one pair's report-level 2x2 table over the resolved population."""

    latest = resolved_latest_report_keys_cte()
    drugs = drug_report_presence_cte(latest)
    reactions = reaction_report_presence_cte(latest)
    selected_drugs = (
        select(drugs.c.primary_id)
        .where(drugs.c.drug_name == drug_name)
        .cte("selected_drug_report_presence")
    )
    selected_reactions = (
        select(reactions.c.primary_id)
        .where(reactions.c.reaction_term == reaction_term)
        .cte("selected_reaction_report_presence")
    )
    classified = (
        select(
            latest.c.primary_id,
            case((selected_drugs.c.primary_id.is_not(None), 1), else_=0).label("drug_present"),
            case((selected_reactions.c.primary_id.is_not(None), 1), else_=0).label(
                "reaction_present"
            ),
        )
        .outerjoin(selected_drugs, selected_drugs.c.primary_id == latest.c.primary_id)
        .outerjoin(selected_reactions, selected_reactions.c.primary_id == latest.c.primary_id)
        .cte("selected_pair_report_classification")
    )

    def count_reports(drug_present: int, reaction_present: int) -> ColumnElement[int]:
        return func.coalesce(
            func.sum(
                case(
                    (
                        (classified.c.drug_present == drug_present)
                        & (classified.c.reaction_present == reaction_present),
                        1,
                    ),
                    else_=0,
                )
            ),
            0,
        )

    return select(
        literal(drug_name).label("drug_name"),
        literal(reaction_term).label("reaction_term"),
        func.count(classified.c.primary_id).label("population_size"),
        count_reports(1, 1).label("a"),
        count_reports(1, 0).label("b"),
        count_reports(0, 1).label("c"),
        count_reports(0, 0).label("d"),
    )


def observed_drug_reaction_contingencies_statement() -> Select[
    tuple[str, str, int, int, int, int, int]
]:
    """Aggregate contingency counts for every observed resolved drug-reaction pair."""

    latest = resolved_latest_report_keys_cte()
    drugs = drug_report_presence_cte(latest)
    reactions = reaction_report_presence_cte(latest)
    pairs = drug_reaction_report_presence_cte(drugs, reactions)
    population_size = select(func.count()).select_from(latest).scalar_subquery()
    drug_counts = (
        select(drugs.c.drug_name, func.count().label("drug_report_count"))
        .group_by(drugs.c.drug_name)
        .cte("drug_report_counts")
    )
    reaction_counts = (
        select(reactions.c.reaction_term, func.count().label("reaction_report_count"))
        .group_by(reactions.c.reaction_term)
        .cte("reaction_report_counts")
    )
    pair_counts = (
        select(
            pairs.c.drug_name,
            pairs.c.reaction_term,
            func.count().label("a"),
        )
        .group_by(pairs.c.drug_name, pairs.c.reaction_term)
        .cte("drug_reaction_pair_counts")
    )
    return (
        select(
            pair_counts.c.drug_name,
            pair_counts.c.reaction_term,
            population_size.label("population_size"),
            pair_counts.c.a,
            (drug_counts.c.drug_report_count - pair_counts.c.a).label("b"),
            (reaction_counts.c.reaction_report_count - pair_counts.c.a).label("c"),
            (
                population_size
                - drug_counts.c.drug_report_count
                - reaction_counts.c.reaction_report_count
                + pair_counts.c.a
            ).label("d"),
        )
        .join(drug_counts, drug_counts.c.drug_name == pair_counts.c.drug_name)
        .join(
            reaction_counts,
            reaction_counts.c.reaction_term == pair_counts.c.reaction_term,
        )
        .order_by(pair_counts.c.a.desc(), pair_counts.c.drug_name, pair_counts.c.reaction_term)
    )
