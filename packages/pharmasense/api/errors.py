"""Sanitized application errors handled at the HTTP boundary."""


class AnalyticsUnavailableError(RuntimeError):
    """Analytics cannot run because required database configuration is unavailable."""


class AnalyticsExecutionError(RuntimeError):
    """An analytics query or result failed without exposing internal database details."""
