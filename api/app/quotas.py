"""Host SaaS quotas (Phase F2) — ingest rate, body size, project storage.

All limits are env-gated; ``0`` disables a check (default for local lean).
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from typing import Optional

from fastapi import HTTPException, Request

from app import config

logger = logging.getLogger("mem_dog.quotas")

# Paths subject to ingest rate limits (POST/PUT/PATCH only).
_INGEST_PATH_PREFIXES = (
    "/api/v1/data",
    "/api/v1/ingest",
    "/api/v1/ai/embeddings",
    "/api/v1/users/",  # .../data uploads
)


class _SlidingWindowLimiter:
    """In-process sliding 60s window keyed by tenant string."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._windows: dict[str, list[float]] = defaultdict(list)

    def check(self, key: str, limit: int) -> tuple[bool, int]:
        """Return (allowed, retry_after_seconds)."""
        if limit <= 0:
            return True, 0
        now = time.monotonic()
        cutoff = now - 60.0
        with self._lock:
            window = [t for t in self._windows[key] if t > cutoff]
            self._windows[key] = window
            if len(window) >= limit:
                oldest = min(window) if window else now
                retry = max(1, int(60.0 - (now - oldest)) + 1)
                return False, retry
            window.append(now)
            self._windows[key] = window
            return True, 0

    def reset(self) -> None:
        with self._lock:
            self._windows.clear()


_ingest_limiter = _SlidingWindowLimiter()


def reset_quotas_for_tests() -> None:
    """Clear in-memory rate windows (tests only)."""
    _ingest_limiter.reset()


def _quota_http(
    *,
    code: str,
    message: str,
    retry_after: int = 60,
    details: Optional[dict] = None,
) -> HTTPException:
    return HTTPException(
        status_code=429,
        detail={
            "code": code,
            "message": message,
            "details": details or {},
        },
        headers={"Retry-After": str(max(1, retry_after))},
    )


def tenant_key_from_request(request: Request) -> str:
    """Prefer authenticated user, else API key prefix, else client IP."""
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return f"user:{user_id}"
    provided = (request.headers.get("x-api-key") or "").strip()
    if provided:
        return f"key:{provided[:16]}"
    client = request.client.host if request.client else "unknown"
    return f"ip:{client}"


def is_ingest_path(path: str, method: str) -> bool:
    if method.upper() not in ("POST", "PUT", "PATCH"):
        return False
    for prefix in _INGEST_PATH_PREFIXES:
        if path == prefix or path.startswith(prefix.rstrip("/") + "/") or path.startswith(prefix):
            # /api/v1/users/{id}/data
            if prefix == "/api/v1/users/":
                return path.endswith("/data") or "/data" in path
            return True
    return False


def check_ingest_rate(request: Request) -> None:
    """Raise 429 rate_limited if ingest RPM exceeded for this tenant."""
    rpm = int(getattr(config, "QUOTA_INGEST_RPM", 0) or 0)
    if rpm <= 0:
        return
    if not is_ingest_path(request.url.path, request.method):
        return
    key = tenant_key_from_request(request)
    allowed, retry = _ingest_limiter.check(key, rpm)
    if not allowed:
        logger.warning("Ingest rate limit exceeded key=%s rpm=%s", key, rpm)
        raise _quota_http(
            code="rate_limited",
            message=f"Ingest rate limit exceeded ({rpm} requests/minute)",
            retry_after=retry,
            details={"limit": rpm, "window_seconds": 60, "tenant": key},
        )


def check_body_size(size_bytes: int) -> None:
    """Raise 429 quota_exceeded if body exceeds QUOTA_MAX_BODY_BYTES."""
    max_bytes = int(getattr(config, "QUOTA_MAX_BODY_BYTES", 0) or 0)
    if max_bytes <= 0:
        return
    if size_bytes > max_bytes:
        raise _quota_http(
            code="quota_exceeded",
            message=f"Request body exceeds max size ({max_bytes} bytes)",
            retry_after=60,
            details={
                "limit_bytes": max_bytes,
                "actual_bytes": size_bytes,
                "quota": "max_body_bytes",
            },
        )


def check_content_length_header(request: Request) -> None:
    """Fast-reject oversized Content-Length before reading the body."""
    max_bytes = int(getattr(config, "QUOTA_MAX_BODY_BYTES", 0) or 0)
    if max_bytes <= 0:
        return
    raw = request.headers.get("content-length")
    if not raw:
        return
    try:
        length = int(raw)
    except ValueError:
        return
    check_body_size(length)


def project_storage_bytes(storage, *, user_id: str, project_id: str) -> int:
    """Sum current sizes of data items in a project for a user."""
    items, _ = storage.list_all_metadata_paginated(
        user_id=user_id, skip=0, limit=10_000, project_id=project_id
    )
    return sum(int(getattr(i, "size", 0) or 0) for i in items)


def check_project_storage(
    storage,
    *,
    user_id: str,
    project_id: Optional[str],
    additional_bytes: int,
) -> None:
    """Raise 429 if project would exceed QUOTA_MAX_STORAGE_BYTES_PER_PROJECT."""
    max_bytes = int(getattr(config, "QUOTA_MAX_STORAGE_BYTES_PER_PROJECT", 0) or 0)
    if max_bytes <= 0 or not project_id or not user_id:
        return
    try:
        used = project_storage_bytes(storage, user_id=user_id, project_id=project_id)
    except Exception as exc:
        logger.warning("project storage check failed: %s", exc)
        return
    if used + additional_bytes > max_bytes:
        raise _quota_http(
            code="quota_exceeded",
            message=f"Project storage quota exceeded ({max_bytes} bytes)",
            retry_after=60,
            details={
                "limit_bytes": max_bytes,
                "used_bytes": used,
                "additional_bytes": additional_bytes,
                "project_id": project_id,
                "quota": "max_storage_bytes_per_project",
            },
        )
