"""Look up a webhook record by ``webhook_id``.

Cache → Supabase fast-path → API fallback.
Mirrors the resolution pattern in ``identity.py``.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from . import config
from . import supabase_reader

_log = logging.getLogger("webhook_gateway.webhook_lookup")

_CACHE_TTL_S = 300  # 5 minutes
_TIMEOUT_S = 10.0

_cache: dict[str, tuple[dict[str, Any] | None, float]] = {}


def _try_supabase(webhook_id: str) -> dict[str, Any] | None:
    """Direct Supabase read. Returns webhook record dict or None."""
    if not supabase_reader.is_available():
        return None
    client = supabase_reader._get_client()
    if client is None:
        return None
    try:
        res = (
            client.table("webhooks")
            .select("*")
            .eq("webhook_id", webhook_id)
            .limit(1)
            .execute()
        )
        if res.data:
            return res.data[0]
        return None
    except Exception as exc:
        _log.debug("Supabase webhook lookup failed for %s: %s", webhook_id, exc)
        return None


async def get_webhook(webhook_id: str) -> dict[str, Any] | None:
    """Return the webhook record or None if not found."""
    # Cache check
    cached = _cache.get(webhook_id)
    if cached is not None:
        record, ts = cached
        if time.monotonic() - ts < _CACHE_TTL_S:
            return record
        del _cache[webhook_id]

    # Fast path: Supabase direct read
    record = _try_supabase(webhook_id)
    if record is not None:
        _cache[webhook_id] = (record, time.monotonic())
        return record

    # Fallback: mem-dog API
    if not config.MEM_DOG_API_URL:
        return None
    url = f"{config.MEM_DOG_API_URL}/api/v1/webhooks/{webhook_id}"
    headers: dict[str, str] = {}
    if config.MEM_DOG_API_KEY:
        headers["x-api-key"] = config.MEM_DOG_API_KEY
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
            resp = await client.get(url, headers=headers)
        if resp.status_code == 200:
            record = resp.json()
            _cache[webhook_id] = (record, time.monotonic())
            return record
    except Exception as exc:
        _log.warning("API webhook lookup failed for %s: %s", webhook_id, exc)

    return None


def invalidate(webhook_id: str) -> None:
    """Remove a single webhook from the cache."""
    _cache.pop(webhook_id, None)


def clear_cache() -> None:
    """Flush the entire webhook cache (useful in tests)."""
    _cache.clear()
