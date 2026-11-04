"""Versioned read-only routes exposing existing FAERS analytics services."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from pharmasense.analytics.prioritization import SignalThresholds
from pharmasense.api.dependencies import get_analytics_service
from pharmasense.api.schemas.analytics import (
    DrugListResponse,
    DrugReactionListResponse,
    DrugReactionSummaryResponse,
    DrugSummaryResponse,
    ErrorResponse,
    SignalDetailResponse,
    SignalListResponse,
    SignalResponse,
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
