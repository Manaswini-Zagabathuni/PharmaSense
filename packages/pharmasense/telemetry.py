"""Dependency-free, privacy-conscious structured event helpers."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from time import perf_counter

type LogValue = str | int | float | bool | None


def configure_application_logging(level: str) -> None:
    """Configure local JSON-message output without replacing deployment handlers."""

    logging.basicConfig(level=level, format="%(message)s")
    logging.getLogger("pharmasense").setLevel(level)


def structured_log(
    target: logging.Logger,
    event: str,
    *,
    level: int = logging.INFO,
    **fields: LogValue,
) -> None:
    """Write a deterministic JSON event containing only caller-selected safe fields."""

    target.log(
        level,
        json.dumps({"event": event, **fields}, separators=(",", ":"), sort_keys=True),
    )


@contextmanager
def timed_operation(target: logging.Logger, operation: str) -> Iterator[None]:
    """Log one stable operation name, outcome, and monotonic duration."""

    started_at = perf_counter()
    outcome = "error"
    try:
        yield
        outcome = "success"
    finally:
        duration_ms = max(0.0, (perf_counter() - started_at) * 1000)
        structured_log(
            target,
            "analytics_operation_completed",
            operation=operation,
            outcome=outcome,
            duration_ms=round(duration_ms, 3),
        )
