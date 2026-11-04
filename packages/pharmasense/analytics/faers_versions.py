"""Read-only FAERS latest-report-version resolution queries."""

from __future__ import annotations

from enum import StrEnum

from sqlalchemy import BigInteger, case, cast, func, select
from sqlalchemy.sql import Select
from sqlalchemy.sql.selectable import CTE

from pharmasense.db.models import FaersReportVersion

_NUMERIC_VERSION_PATTERN = r"^[0-9]+$"


class ReportVersionResolutionStatus(StrEnum):
    """Case-level outcomes for strict latest-version resolution."""

    RESOLVED = "RESOLVED"
    INVALID_VERSION = "INVALID_VERSION"
    VERSION_TIE = "VERSION_TIE"


def _classified_report_versions() -> CTE:
    """Build classified immutable versions as private composable CTEs."""

    numeric_version = case(
        (
            FaersReportVersion.case_version.regexp_match(_NUMERIC_VERSION_PATTERN),
            cast(FaersReportVersion.case_version, BigInteger),
        ),
        else_=None,
    ).label("numeric_version")
    parsed = select(
        FaersReportVersion.primary_id,
        FaersReportVersion.case_id,
        numeric_version,
    ).cte("faers_parsed_report_versions")
    with_maximum = select(
        parsed.c.primary_id,
        parsed.c.case_id,
        parsed.c.numeric_version,
        func.max(parsed.c.numeric_version)
        .over(partition_by=parsed.c.case_id)
        .label("maximum_numeric_version"),
    ).cte("faers_report_versions_with_maximum")
    return select(
        with_maximum.c.primary_id,
        with_maximum.c.case_id,
        with_maximum.c.numeric_version,
        with_maximum.c.maximum_numeric_version,
        func.sum(
            case(
                (
                    with_maximum.c.numeric_version == with_maximum.c.maximum_numeric_version,
                    1,
                ),
                else_=0,
            )
        )
        .over(partition_by=with_maximum.c.case_id)
        .label("maximum_version_count"),
    ).cte("faers_classified_report_versions")


def latest_report_versions_statement() -> Select[tuple[FaersReportVersion]]:
    """Select one unambiguous maximum numeric CASEVERSION per longitudinal case.

    The statement is read-only and deliberately excludes cases whose versions are all invalid or
    whose maximum numeric value is shared by multiple immutable reports.
    """

    classified = _classified_report_versions()
    return (
        select(FaersReportVersion)
        .join(classified, classified.c.primary_id == FaersReportVersion.primary_id)
        .where(
            classified.c.numeric_version == classified.c.maximum_numeric_version,
            classified.c.maximum_version_count == 1,
        )
    )


def report_version_resolution_statement() -> Select[tuple[str, str, int | None, int]]:
    """Select one diagnostic resolution row for every longitudinal FAERS case."""

    classified = _classified_report_versions()
    resolution_status = case(
        (
            classified.c.maximum_numeric_version.is_(None),
            ReportVersionResolutionStatus.INVALID_VERSION.value,
        ),
        (
            classified.c.maximum_version_count > 1,
            ReportVersionResolutionStatus.VERSION_TIE.value,
        ),
        else_=ReportVersionResolutionStatus.RESOLVED.value,
    ).label("resolution_status")
    return (
        select(
            classified.c.case_id,
            resolution_status,
            classified.c.maximum_numeric_version,
            classified.c.maximum_version_count,
        )
        .distinct()
        .order_by(classified.c.case_id)
    )
