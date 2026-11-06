"""Dependency-free HTTP response hardening middleware."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Request, Response

type RequestHandler = Callable[[Request], Awaitable[Response]]

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


async def add_security_headers(request: Request, call_next: RequestHandler) -> Response:
    """Apply a fixed, API-safe set of browser security headers."""

    response = await call_next(request)
    for name, value in SECURITY_HEADERS.items():
        response.headers[name] = value
    return response
