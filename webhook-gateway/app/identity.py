"""Resolve a channel-specific identity to a mem-dog ``user_id``.

When Supabase direct-read is configured, queries the ``mem_dog_blobs``
table directly.  Otherwise falls back to
``GET /api/v1/channel-identities/by-channel/{type}/{unique_id}``
on the mem-dog API.  Results are cached in-process for 5 minutes.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from . import config
from . import supabase_reader

_log = logging.getLogger("openclaw_gateway.identity")

_CACHE_TTL_S = 300  # 5 minutes
_TIMEOUT_S = 10.0

_cache: dict[str, tuple[str, float]] = {}

_IDENTITY_PREFIX = "_channel_identities/by_channel"


def _cache_key(channel_type: str, channel_unique_id: str) -> str:
    return f"{channel_type}:{channel_unique_id}"


def _safe_segment(raw: str) -> str:
    """Replicate the API's path-safe segment logic."""
    return (raw or "unknown").replace("/", "_").replace("\\", "_").strip()


def _try_supabase(channel_type: str, channel_unique_id: str) -> str | None:
    """Attempt direct Supabase read. Returns user_id or None to signal fallback."""
    if not supabase_reader.is_available():
        return None
    ct_safe = _safe_segment(channel_type)
    id_safe = _safe_segment(channel_unique_id)
    path = f"{_IDENTITY_PREFIX}/{ct_safe}/{id_safe}"
    data = supabase_reader.read_blob_json("meta", path)
    if data is None:
        return None
    return data.get("user_id")


async def resolve_user_id(
    channel_type: str,
    channel_unique_id: str,
) -> str:
    """Return the ``user_id`` for (*channel_type*, *channel_unique_id*).

    Falls back to ``config.DEFAULT_USER_ID`` when the identity is not
    found or the API is unreachable.
    """
    if not channel_unique_id:
        return config.DEFAULT_USER_ID

    key = _cache_key(channel_type, channel_unique_id)
    cached = _cache.get(key)
    if cached:
        uid, ts = cached
        if time.monotonic() - ts < _CACHE_TTL_S:
            return uid
        del _cache[key]

    # Fast path: direct Supabase read
    uid = _try_supabase(channel_type, channel_unique_id)
    if uid is not None:
        _cache[key] = (uid, time.monotonic())
        return uid

    # Fallback: mem-dog API
    if not config.MEM_DOG_API_URL:
        return config.DEFAULT_USER_ID

    url = (
        f"{config.MEM_DOG_API_URL}/api/v1/channel-identities"
        f"/by-channel/{channel_type}/{channel_unique_id}"
    )
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
            resp = await client.get(url)
        if resp.status_code == 200:
            data: dict[str, Any] = resp.json()
            uid = data.get("user_id", config.DEFAULT_USER_ID)
            _cache[key] = (uid, time.monotonic())
            return uid
    except Exception as exc:
        _log.warning("Identity lookup failed for %s/%s: %s", channel_type, channel_unique_id, exc)

    return config.DEFAULT_USER_ID


def clear_cache() -> None:
    """Flush the in-process identity cache (useful in tests)."""
    _cache.clear()
