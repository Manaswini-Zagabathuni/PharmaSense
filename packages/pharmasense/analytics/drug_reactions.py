"""Read-only drug and drug-reaction summaries for resolved latest FAERS reports."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.sql import Select
from sqlalchemy.sql.selectable import CTE

from pharmasense.analytics.faers_versions import latest_report_versions_statement
from pharmasense.db.models import FaersDrug, FaersReaction


def _latest_report_keys() -> CTE:
    """Return the Phase 2A population at its report-and-case key grain."""

    latest = latest_report_versions_statement().subquery("resolved_latest_report_versions")
    return select(latest.c.primary_id, latest.c.case_id).cte("resolved_latest_report_keys")


def _drug_report_presence(latest: CTE | None = None) -> CTE:
    """Return one row per resolved report, case, and source drug-name group."""

    if latest is None:
        latest = _latest_report_keys()
    return (
        select(
            latest.c.primary_id,
            latest.c.case_id,
            FaersDrug.drugname.label("drug_name"),
        )
        .join(FaersDrug, FaersDrug.primary_id == latest.c.primary_id)
        .distinct()
        .cte("drug_report_presence")
    )


def _reaction_report_presence(latest: CTE) -> CTE:
    """Return one row per resolved report, case, and source reaction-term group."""

    return (
        select(
            latest.c.primary_id,
            latest.c.case_id,
            FaersReaction.pt.label("reaction_term"),
        )
        .join(FaersReaction, FaersReaction.primary_id == latest.c.primary_id)
        .distinct()
        .cte("reaction_report_presence")
    )


def _drug_reaction_report_presence() -> CTE:
    """Return one row per resolved report, drug-name group, and reaction-term group."""

    latest = _latest_report_keys()
    drugs = _drug_report_presence(latest)
    reactions = _reaction_report_presence(latest)
    return (
        select(
            drugs.c.primary_id,
            drugs.c.case_id,
            drugs.c.drug_name,
            reactions.c.reaction_term,
        )
        .join(
            reactions,
            (reactions.c.primary_id == drugs.c.primary_id)
            & (reactions.c.case_id == drugs.c.case_id),
        )
        .cte("drug_reaction_report_presence")
    )


def drug_summary_statement() -> Select[tuple[str, int, int]]:
    """Count resolved latest reports and cases containing each source drug-name group."""

    presence = _drug_report_presence()
    return (
        select(
            presence.c.drug_name,
            func.count(presence.c.primary_id).label("report_count"),
            func.count(func.distinct(presence.c.case_id)).label("case_count"),
        )
        .group_by(presence.c.drug_name)
        .order_by(func.count(presence.c.primary_id).desc(), presence.c.drug_name)
    )


def _drug_reaction_summary_statement(
    drug_name: str | None = None,
) -> Select[tuple[str, str, int, int]]:
    presence = _drug_reaction_report_presence()
    statement = (
        select(
            presence.c.drug_name,
            presence.c.reaction_term,
            func.count(presence.c.primary_id).label("report_count"),
            func.count(func.distinct(presence.c.case_id)).label("case_count"),
        )
        .group_by(presence.c.drug_name, presence.c.reaction_term)
        .order_by(
            func.count(presence.c.primary_id).desc(),
            presence.c.drug_name,
            presence.c.reaction_term,
        )
    )
    if drug_name is not None:
        statement = statement.where(presence.c.drug_name == drug_name)
    return statement


def drug_reaction_summary_statement() -> Select[tuple[str, str, int, int]]:
    """Count resolved latest reports and cases containing each drug-reaction pair."""

    return _drug_reaction_summary_statement()


def most_reported_reactions_for_drug_statement(
    drug_name: str, *, limit: int | None = None
) -> Select[tuple[str, str, int, int]]:
    """Rank co-reported reaction terms for one source drug-name filter."""

    if limit is not None and limit < 1:
        raise ValueError("limit must be a positive integer or None")

    statement = _drug_reaction_summary_statement(drug_name)
    if limit is not None:
        statement = statement.limit(limit)
    return statement
