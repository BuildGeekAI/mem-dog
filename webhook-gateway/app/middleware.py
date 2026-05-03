"""Security middleware for the Webhook Gateway.

Provides:
- API key authentication (``WGW_API_KEY``)
- IP allowlisting (``WGW_ALLOWED_IPS``)
- Simple sliding-window rate limiting (``WGW_RATE_LIMIT``)
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from . import config

_log = logging.getLogger("webhook_gateway.middleware")

PUBLIC_PATHS = frozenset({"/", "/health", "/ready", "/docs", "/openapi.json", "/redoc"})


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class ApiKeyAuthMiddleware(BaseHTTPMiddleware):
    """Reject requests that don't carry a valid API key.

    Skips health/docs endpoints so load balancers and discovery still work.
    The key is checked in order: ``Authorization: Bearer <key>``,
    ``x-api-key`` header, ``api_key`` query parameter.

    When ``WGW_API_KEY`` is empty, authentication is disabled (open mode).
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        api_key = config.WGW_API_KEY
        if not api_key:
            return await call_next(request)

        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)

        # Extract the token from multiple locations
        token = None
        auth_header = request.headers.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            token = auth_header[7:].strip()
        if not token:
            token = request.headers.get("x-api-key")
        if not token:
            token = request.query_params.get("api_key")

        if token != api_key:
            ip = _client_ip(request)
            _log.warning("Unauthorized request from %s to %s", ip, request.url.path)
            return JSONResponse(
                {"detail": "Invalid or missing API key"},
                status_code=401,
            )

        return await call_next(request)


class IpAllowlistMiddleware(BaseHTTPMiddleware):
    """Restrict access to a set of allowed IP addresses or CIDR ranges.

    When ``WGW_ALLOWED_IPS`` is empty, all IPs are permitted.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        allowed = config.WGW_ALLOWED_IPS
        if not allowed:
            return await call_next(request)

        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)

        ip = _client_ip(request)
        if ip not in allowed:
            _log.warning("Blocked request from disallowed IP %s to %s", ip, request.url.path)
            return JSONResponse(
                {"detail": "Forbidden"},
                status_code=403,
            )

        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory sliding-window rate limiter per client IP.

    ``WGW_RATE_LIMIT`` sets the max requests per minute (0 = disabled).
    """

    def __init__(self, app, *, requests_per_minute: int = 0) -> None:  # type: ignore[override]
        super().__init__(app)
        self.rpm = requests_per_minute or config.WGW_RATE_LIMIT
        self._windows: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if self.rpm <= 0:
            return await call_next(request)

        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)

        ip = _client_ip(request)
        now = time.monotonic()
        window = self._windows[ip]

        # Prune entries older than 60 seconds
        cutoff = now - 60.0
        self._windows[ip] = window = [t for t in window if t > cutoff]

        if len(window) >= self.rpm:
            _log.warning("Rate limit exceeded for %s (%d req/min)", ip, self.rpm)
            return JSONResponse(
                {"detail": f"Rate limit exceeded ({self.rpm} req/min)"},
                status_code=429,
                headers={"Retry-After": "60"},
            )

        window.append(now)
        return await call_next(request)
