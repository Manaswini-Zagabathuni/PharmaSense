"""Read-only source inventory and reproducible loaded-quarter analytics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from sqlalchemy import case, distinct, func, select
from sqlalchemy.sql import Select
from sqlalchemy.sql.elements import ColumnElement

from pharmasense.analytics.faers_versions import (
    ReportPopulationFilter,
    ReportVersionResolutionStatus,
    report_version_resolution_statement,
)
from pharmasense.analytics.prioritization import SignalResult
from pharmasense.db.models import FaersReportVersion, IngestionRun, SourceArtifact


@dataclass(frozen=True, order=True)
class SourceQuarter:
    """Validated calendar-quarter identifier used by historical analytics."""

    year: int
    quarter: int

    def __post_init__(self) -> None:
        if type(self.year) is not int or self.year < 1900 or self.year > 9999:
            raise ValueError("source year must be an integer between 1900 and 9999")
        if type(self.quarter) is not int or self.quarter not in (1, 2, 3, 4):
            raise ValueError("source quarter must be an integer between 1 and 4")

    @property
    def identifier(self) -> str:
        """Return the stable external representation, for example ``2023Q4``."""

        return f"{self.year:04d}Q{self.quarter}"

    @property
    def ordinal(self) -> int:
        """Return a monotonically increasing value suitable for range validation."""

        return self.year * 4 + self.quarter - 1

    @classmethod
    def parse(cls, value: str) -> SourceQuarter:
        """Parse the strict external quarter representation."""

        if len(value) != 6 or value[4] != "Q" or not value[:4].isdigit():
            raise ValueError("source quarter must use YYYYQ1 through YYYYQ4 format")
        quarter_text = value[5]
        if quarter_text not in "1234":
            raise ValueError("source quarter must use YYYYQ1 through YYYYQ4 format")
        return cls(int(value[:4]), int(quarter_text))


class HistoricalPopulationSelectionRule(StrEnum):
    """Stable identifier for the Phase 5A loaded-source population rule."""

    COMPLETED_INGESTIONS_IN_INCLUSIVE_QUARTER_RANGE = (
        "COMPLETED_INGESTIONS_IN_INCLUSIVE_QUARTER_RANGE"
    )


@dataclass(frozen=True)
class SourceSnapshotRecord:
    """Safe provenance and load-state metadata for one immutable archive."""

    source_quarter: SourceQuarter
    source_name: str
    filename: str
    archive_sha256: str
    retrieved_at: datetime
    completed_ingestion_runs: int
    latest_completed_at: datetime | None
    persisted_report_count: int
    successfully_loaded_report_count: int
    successfully_loaded_case_count: int

    @property
    def known_in_provenance(self) -> bool:
        return True

    @property
    def contains_successfully_loaded_reports(self) -> bool:
        return self.successfully_loaded_report_count > 0


@dataclass(frozen=True)
class HistoricalAnalysisMetadata:
    """Exact population definition and inherited Phase 2A exclusions."""

    selection_rule: HistoricalPopulationSelectionRule
    requested_start_quarter: SourceQuarter
    requested_end_quarter: SourceQuarter
    selected_source_quarters: tuple[SourceQuarter, ...]
    resolved_report_count: int
    resolved_case_count: int
    excluded_invalid_version_case_count: int
    excluded_version_tie_case_count: int


@dataclass(frozen=True)
class QuarterSignalResult:
    """One independently resolved source-quarter signal measurement."""

    source_quarter: SourceQuarter
    signal: SignalResult


@dataclass(frozen=True)
class HistoricalSignalResult:
    """Signal history plus the reproducible range-level population metadata."""

    metadata: HistoricalAnalysisMetadata
    quarters: tuple[QuarterSignalResult, ...]


def source_snapshot_inventory_statement() -> Select[tuple[object, ...]]:
    """Return archive-level provenance with persisted and completed-run report counts."""

    report_counts = (
        select(
            IngestionRun.artifact_id.label("artifact_id"),
            func.count(distinct(FaersReportVersion.primary_id)).label("persisted_report_count"),
            func.count(
                distinct(
                    case(
                        (IngestionRun.status == "COMPLETED", FaersReportVersion.primary_id),
                        else_=None,
                    )
                )
            ).label("successfully_loaded_report_count"),
            func.count(
                distinct(
                    case(
                        (IngestionRun.status == "COMPLETED", FaersReportVersion.case_id),
                        else_=None,
                    )
                )
            ).label("successfully_loaded_case_count"),
        )
        .outerjoin(
            FaersReportVersion,
            FaersReportVersion.ingestion_run_id == IngestionRun.id,
        )
        .group_by(IngestionRun.artifact_id)
        .cte("source_artifact_report_counts")
    )
    run_counts = (
        select(
            IngestionRun.artifact_id.label("artifact_id"),
            func.sum(case((IngestionRun.status == "COMPLETED", 1), else_=0)).label(
                "completed_ingestion_runs"
            ),
            func.max(
                case(
                    (IngestionRun.status == "COMPLETED", IngestionRun.finished_at),
                    else_=None,
                )
            ).label("latest_completed_at"),
        )
        .group_by(IngestionRun.artifact_id)
        .cte("source_artifact_run_counts")
    )
    return (
        select(
            SourceArtifact.source_year,
            SourceArtifact.source_quarter,
            SourceArtifact.source_name,
            SourceArtifact.filename,
            SourceArtifact.sha256.label("archive_sha256"),
            SourceArtifact.retrieved_at,
            func.coalesce(run_counts.c.completed_ingestion_runs, 0).label(
                "completed_ingestion_runs"
            ),
            run_counts.c.latest_completed_at,
            func.coalesce(report_counts.c.persisted_report_count, 0).label(
                "persisted_report_count"
            ),
            func.coalesce(report_counts.c.successfully_loaded_report_count, 0).label(
                "successfully_loaded_report_count"
            ),
            func.coalesce(report_counts.c.successfully_loaded_case_count, 0).label(
                "successfully_loaded_case_count"
            ),
        )
        .outerjoin(report_counts, report_counts.c.artifact_id == SourceArtifact.id)
        .outerjoin(run_counts, run_counts.c.artifact_id == SourceArtifact.id)
        .order_by(
            SourceArtifact.source_year,
            SourceArtifact.source_quarter,
            SourceArtifact.filename,
            SourceArtifact.sha256,
        )
    )


def successfully_loaded_quarters_statement(
    start: SourceQuarter, end: SourceQuarter
) -> Select[tuple[int, int]]:
    """Select deterministic quarters backed by at least one completed-run report."""

    if start > end:
        raise ValueError("start quarter must not follow end quarter")
    report_ordinal = FaersReportVersion.source_year * 4 + FaersReportVersion.source_quarter - 1
    return (
        select(FaersReportVersion.source_year, FaersReportVersion.source_quarter)
        .join(IngestionRun, IngestionRun.id == FaersReportVersion.ingestion_run_id)
        .where(
            IngestionRun.status == "COMPLETED",
            report_ordinal >= start.ordinal,
            report_ordinal <= end.ordinal,
        )
        .distinct()
        .order_by(FaersReportVersion.source_year, FaersReportVersion.source_quarter)
    )


def historical_population_filter(
    quarters: tuple[SourceQuarter, ...],
) -> ReportPopulationFilter:
    """Translate selected loaded quarters into the shared Phase 2A resolver boundary."""

    return ReportPopulationFilter(
        tuple((quarter.year, quarter.quarter) for quarter in quarters),
        completed_ingestions_only=True,
    )


def historical_resolution_summary_statement(
    quarters: tuple[SourceQuarter, ...],
) -> Select[tuple[int, int, int, int]]:
    """Summarize resolved cases and explicit Phase 2A exclusions for selected quarters."""

    resolutions = report_version_resolution_statement(
        historical_population_filter(quarters)
    ).subquery("historical_report_version_resolutions")

    def status_count(status: ReportVersionResolutionStatus) -> ColumnElement[int]:
        return func.coalesce(
            func.sum(case((resolutions.c.resolution_status == status.value, 1), else_=0)),
            0,
        )

    resolved_count = status_count(ReportVersionResolutionStatus.RESOLVED)
    return select(
        resolved_count.label("resolved_report_count"),
        resolved_count.label("resolved_case_count"),
        status_count(ReportVersionResolutionStatus.INVALID_VERSION).label(
            "excluded_invalid_version_case_count"
        ),
        status_count(ReportVersionResolutionStatus.VERSION_TIE).label(
            "excluded_version_tie_case_count"
        ),
    )
