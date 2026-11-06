"""Privacy-conscious request and operation observability helpers."""

from __future__ import annotations

import logging
import re
from collections.abc import Awaitable, Callable
from time import perf_counter
from uuid import uuid4

from fastapi import Request, Response

from pharmasense.telemetry import structured_log

REQUEST_ID_HEADER = "X-Request-ID"
_REQUEST_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")

type RequestHandler = Callable[[Request], Awaitable[Response]]

logger = logging.getLogger(__name__)


def request_id_for(value: str | None) -> str:
    """Preserve a bounded safe request ID or generate a random local identifier."""

    if value is not None and _REQUEST_ID_PATTERN.fullmatch(value) is not None:
        return value
    return uuid4().hex


def safe_request_path(request: Request) -> str:
    """Return the matched route template without path-parameter source values."""

    route = request.scope.get("route")
    route_path = getattr(route, "path", None)
    return route_path if isinstance(route_path, str) else "<unmatched>"


async def observe_request(request: Request, call_next: RequestHandler) -> Response:
    """Attach a request ID and log safe request completion fields."""

    request_id = request_id_for(request.headers.get(REQUEST_ID_HEADER))
    request.state.request_id = request_id
    started_at = perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
    finally:
        duration_ms = max(0.0, (perf_counter() - started_at) * 1000)
        structured_log(
            logger,
            "http_request_completed",
            request_id=request_id,
            method=request.method,
            path=safe_request_path(request),
            status_code=status_code,
            duration_ms=round(duration_ms, 3),
        )
