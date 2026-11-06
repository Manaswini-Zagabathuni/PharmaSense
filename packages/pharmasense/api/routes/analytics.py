"""Versioned read-only routes exposing existing FAERS analytics services."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from pharmasense.analytics.historical import SourceQuarter
from pharmasense.analytics.prioritization import SignalThresholds
from pharmasense.api.dependencies import get_analytics_service
from pharmasense.api.schemas.analytics import (
    DrugListResponse,
    DrugReactionListResponse,
    DrugReactionSummaryResponse,
    DrugSummaryResponse,
    ErrorResponse,
    HistoricalAnalysisMetadataResponse,
    HistoricalSignalResponse,
    QuarterSignalResponse,
    SignalDetailResponse,
    SignalListResponse,
    SignalResponse,
    SourceSnapshotListResponse,
    SourceSnapshotResponse,
    SourceTermResponse,
    TermDiscoveryResponse,
)
from pharmasense.api.services.analytics import AnalyticsService

router = APIRouter()

_RESEARCH_NOTICE = (
    "FAERS reporting patterns do not establish causality or incidence and are not for clinical "
    "decision-making."
)
_MAX_RESULT_LIMIT = 100
_MAX_DRUG_LIMIT = 200
_MAX_OFFSET = 1_000_000
_MAX_THRESHOLD = 2**63 - 1
_MAX_RATIO_THRESHOLD = 1_000_000.0
_MAX_TERM_LENGTH = 1000
_MAX_SNAPSHOT_LIMIT = 200
_MAX_HISTORICAL_QUARTERS = 80
_MIN_DISCOVERY_QUERY_LENGTH = 2
_MAX_DISCOVERY_QUERY_LENGTH = 200
_MAX_DISCOVERY_LIMIT = 25
_HISTORICAL_METHOD_NOTICE = (
    "Results filter report rows currently loaded from completed source-quarter ingestions. "
    "They are not a retrospective as-of reconstruction of every FDA snapshot."
)
_SOURCE_TERM_NOTICE = (
    "Returned terms are source-derived FAERS values, not normalized clinical concepts, synonym "
    "mappings, or recommendations."
)


def _parse_source_quarter(value: str) -> SourceQuarter:
    try:
        return SourceQuarter.parse(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc


def _normalize_discovery_query(query: str) -> str:
    normalized = query.strip()
    if len(normalized) < _MIN_DISCOVERY_QUERY_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"Discovery query must contain at least {_MIN_DISCOVERY_QUERY_LENGTH} "
                "non-whitespace characters."
            ),
        )
    return normalized


@router.get(
    "/signals",
    response_model=SignalListResponse,
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse},
    },
)
def list_signals(
    service: Annotated[AnalyticsService, Depends(get_analytics_service)],
    limit: Annotated[int, Query(ge=1, le=_MAX_RESULT_LIMIT)] = 25,
    minimum_pair_reports: Annotated[int, Query(ge=1, le=_MAX_THRESHOLD)] = 3,
    minimum_population: Annotated[int | None, Query(ge=1, le=_MAX_THRESHOLD)] = None,
    minimum_ror_lower_bound: Annotated[float, Query(ge=0, le=_MAX_RATIO_THRESHOLD)] = 1.0,
) -> SignalListResponse:
    """Return a bounded lower-confidence-bound-ranked set of prioritized signals."""

    thresholds = SignalThresholds(
        minimum_pair_reports=minimum_pair_reports,
        minimum_population=minimum_population,
        minimum_ror_lower_bound=minimum_ror_lower_bound,
    )
    results = service.list_prioritized_signals(limit=limit, thresholds=thresholds)
    items = [SignalResponse.model_validate(result) for result in results]
    return SignalListResponse(
        items=items,
        returned_count=len(items),
        limit=limit,
        research_notice=_RESEARCH_NOTICE,
    )


@router.get(
    "/signals/{drug_name}/reactions/{reaction_term}",
    response_model=SignalDetailResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse},
    },
)
def signal_detail(
    drug_name: Annotated[str, Path(min_length=1, max_length=_MAX_TERM_LENGTH)],
    reaction_term: Annotated[str, Path(min_length=1, max_length=_MAX_TERM_LENGTH)],
    service: Annotated[AnalyticsService, Depends(get_analytics_service)],
) -> SignalDetailResponse:
    """Return default-threshold diagnostics for one observed co-reporting pair."""

    result = service.get_signal(drug_name, reaction_term)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Drug-reaction pair was not observed in the resolved analytics population.",
        )
    return SignalDetailResponse(
        signal=SignalResponse.model_validate(result),
        research_notice=_RESEARCH_NOTICE,
    )


@router.get(
    "/drugs",
    response_model=DrugListResponse,
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse},
    },
)
def list_drugs(
    service: Annotated[AnalyticsService, Depends(get_analytics_service)],
    limit: Annotated[int, Query(ge=1, le=_MAX_DRUG_LIMIT)] = 50,
    offset: Annotated[int, Query(ge=0, le=_MAX_OFFSET)] = 0,
) -> DrugListResponse:
    """Return one bounded deterministic page of resolved-population drug summaries."""

    records = service.list_drugs(limit=limit, offset=offset)
    items = [DrugSummaryResponse.model_validate(record) for record in records]
    return DrugListResponse(
        items=items,
        returned_count=len(items),
        limit=limit,
        offset=offset,
        research_notice=_RESEARCH_NOTICE,
    )


@router.get(
    "/drugs/{drug_name}/reactions",
    response_model=DrugReactionListResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse},
    },
)
def drug_reactions(
    drug_name: Annotated[str, Path(min_length=1, max_length=_MAX_TERM_LENGTH)],
    service: Annotated[AnalyticsService, Depends(get_analytics_service)],
    limit: Annotated[int, Query(ge=1, le=_MAX_RESULT_LIMIT)] = 25,
) -> DrugReactionListResponse:
    """Return bounded Phase 2B reaction summaries for one resolved-population drug."""

    records = service.list_drug_reactions(drug_name, limit=limit)
    if records is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Drug was not found in the resolved analytics population.",
        )
    items = [DrugReactionSummaryResponse.model_validate(record) for record in records]
    return DrugReactionListResponse(
        drug_name=drug_name,
        items=items,
        returned_count=len(items),
        limit=limit,
        research_notice=_RESEARCH_NOTICE,
    )


@router.get(
    "/discovery/drugs",
    response_model=TermDiscoveryResponse,
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse},
    },
)
def discover_drugs(
    service: Annotated[AnalyticsService, Depends(get_analytics_service)],
    q: Annotated[
        str,
        Query(min_length=_MIN_DISCOVERY_QUERY_LENGTH, max_length=_MAX_DISCOVERY_QUERY_LENGTH),
    ],
    limit: Annotated[int, Query(ge=1, le=_MAX_DISCOVERY_LIMIT)] = 10,
) -> TermDiscoveryResponse:
    """Return bounded resolved-population source drug-name suggestions."""

    records = service.discover_drug_terms(_normalize_discovery_query(q), limit=limit)
    return TermDiscoveryResponse(
        items=[SourceTermResponse.model_validate(record) for record in records],
        returned_count=len(records),
        limit=limit,
        research_notice=_RESEARCH_NOTICE,
        source_term_notice=_SOURCE_TERM_NOTICE,
    )


@router.get(
    "/discovery/reactions",
    response_model=TermDiscoveryResponse,
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse},
    },
)
def discover_reactions(
    service: Annotated[AnalyticsService, Depends(get_analytics_service)],
    q: Annotated[
        str,
        Query(min_length=_MIN_DISCOVERY_QUERY_LENGTH, max_length=_MAX_DISCOVERY_QUERY_LENGTH),
    ],
    limit: Annotated[int, Query(ge=1, le=_MAX_DISCOVERY_LIMIT)] = 10,
) -> TermDiscoveryResponse:
    """Return bounded resolved-population source reaction-term suggestions."""

    records = service.discover_reaction_terms(_normalize_discovery_query(q), limit=limit)
    return TermDiscoveryResponse(
        items=[SourceTermResponse.model_validate(record) for record in records],
        returned_count=len(records),
        limit=limit,
        research_notice=_RESEARCH_NOTICE,
        source_term_notice=_SOURCE_TERM_NOTICE,
    )


@router.get(
    "/source-snapshots",
    response_model=SourceSnapshotListResponse,
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse},
    },
)
def source_snapshots(
    service: Annotated[AnalyticsService, Depends(get_analytics_service)],
    limit: Annotated[int, Query(ge=1, le=_MAX_SNAPSHOT_LIMIT)] = 100,
) -> SourceSnapshotListResponse:
    """Return safe provenance and completed-load state for known source archives."""

    records = service.list_source_snapshots(limit=limit)
    items = [
        SourceSnapshotResponse(
            source_quarter=record.source_quarter.identifier,
            source_name=record.source_name,
            filename=record.filename,
            archive_sha256=record.archive_sha256,
            retrieved_at=record.retrieved_at,
            known_in_provenance=record.known_in_provenance,
            completed_ingestion_runs=record.completed_ingestion_runs,
            latest_completed_at=record.latest_completed_at,
            persisted_report_count=record.persisted_report_count,
            successfully_loaded_report_count=record.successfully_loaded_report_count,
            successfully_loaded_case_count=record.successfully_loaded_case_count,
            contains_successfully_loaded_reports=record.contains_successfully_loaded_reports,
        )
        for record in records
    ]
    return SourceSnapshotListResponse(items=items, returned_count=len(items), limit=limit)


@router.get(
    "/historical/signals/{drug_name}/reactions/{reaction_term}",
    response_model=HistoricalSignalResponse,
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse},
    },
)
def historical_signal(
    drug_name: Annotated[str, Path(min_length=1, max_length=_MAX_TERM_LENGTH)],
    reaction_term: Annotated[str, Path(min_length=1, max_length=_MAX_TERM_LENGTH)],
    service: Annotated[AnalyticsService, Depends(get_analytics_service)],
    start_quarter: Annotated[str, Query(min_length=6, max_length=6)],
    end_quarter: Annotated[str, Query(min_length=6, max_length=6)],
) -> HistoricalSignalResponse:
    """Return independently resolved quarter measurements for one reporting pair."""

    start = _parse_source_quarter(start_quarter)
    end = _parse_source_quarter(end_quarter)
    if start > end:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="start_quarter must not follow end_quarter",
        )
    if end.ordinal - start.ordinal + 1 > _MAX_HISTORICAL_QUARTERS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"historical range must not exceed {_MAX_HISTORICAL_QUARTERS} quarters",
        )

    result = service.get_historical_signal(
        drug_name,
        reaction_term,
        start_quarter=start,
        end_quarter=end,
    )
    metadata = result.metadata
    return HistoricalSignalResponse(
        metadata=HistoricalAnalysisMetadataResponse(
            selection_rule=metadata.selection_rule,
            requested_start_quarter=metadata.requested_start_quarter.identifier,
            requested_end_quarter=metadata.requested_end_quarter.identifier,
            selected_source_quarters=tuple(
                quarter.identifier for quarter in metadata.selected_source_quarters
            ),
            resolved_report_count=metadata.resolved_report_count,
            resolved_case_count=metadata.resolved_case_count,
            excluded_invalid_version_case_count=(metadata.excluded_invalid_version_case_count),
            excluded_version_tie_case_count=metadata.excluded_version_tie_case_count,
        ),
        items=[
            QuarterSignalResponse(
                source_quarter=item.source_quarter.identifier,
                signal=SignalResponse.model_validate(item.signal),
            )
            for item in result.quarters
        ],
        returned_count=len(result.quarters),
        research_notice=_RESEARCH_NOTICE,
        historical_method_notice=_HISTORICAL_METHOD_NOTICE,
    )
