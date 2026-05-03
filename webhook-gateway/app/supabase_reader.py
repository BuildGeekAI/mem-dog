"""Read-only Supabase client for direct blob reads.

When ``SUPABASE_URL`` and ``SUPABASE_KEY`` are configured, the gateway can
bypass the mem-dog API for high-frequency read operations (identity lookups,
memory existence checks, channel config).  All writes still go through the
mem-dog API to preserve index updates and stats tracking.

If Supabase is not configured or a query fails, callers fall back to the
mem-dog API transparently.
"""

from __future__ import annotations

import base64
import json
import logging
from typing import Any, Optional

from . import config

_log = logging.getLogger("openclaw_gateway.supabase_reader")

_TABLE = "mem_dog_blobs"

_client: Any = None
_init_attempted = False


def is_available() -> bool:
    """True when Supabase direct-read credentials are configured."""
    return bool(config.SUPABASE_URL and config.SUPABASE_KEY)


def _get_client() -> Any:
    """Lazily initialise the Supabase client. Returns None on failure."""
    global _client, _init_attempted
    if _client is not None:
        return _client
    if _init_attempted:
        return None
    _init_attempted = True
    if not is_available():
        return None
    try:
        from supabase import create_client

        _client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
        _log.info("Supabase direct-read client initialised")
        return _client
    except Exception as exc:
        _log.warning("Failed to initialise Supabase client: %s", exc)
        return None


def read_blob(store_name: str, path: str) -> Optional[bytes]:
    """Fetch a single blob by ``(store_name, path)``. Returns None on miss/error."""
    client = _get_client()
    if client is None:
        return None
    try:
        res = (
            client.table(_TABLE)
            .select("content")
            .eq("store_name", store_name)
            .eq("path", path)
            .limit(1)
            .execute()
        )
        if not res.data:
            return None
        raw = res.data[0].get("content")
        if raw is None:
            return None
        return base64.b64decode(raw)
    except Exception as exc:
        _log.debug("read_blob(%s, %s) failed: %s", store_name, path, exc)
        return None


def read_blob_json(store_name: str, path: str) -> Optional[dict[str, Any]]:
    """Convenience: read a blob and parse as JSON. Returns None on miss/error."""
    data = read_blob(store_name, path)
    if data is None:
        return None
    try:
        return json.loads(data.decode("utf-8"))
    except Exception:
        return None


def blob_exists(store_name: str, path: str) -> Optional[bool]:
    """Check if a blob exists. Returns None if Supabase is unavailable (caller should fall back)."""
    client = _get_client()
    if client is None:
        return None
    try:
        res = (
            client.table(_TABLE)
            .select("path")
            .eq("store_name", store_name)
            .eq("path", path)
            .limit(1)
            .execute()
        )
        return bool(res.data)
    except Exception as exc:
        _log.debug("blob_exists(%s, %s) failed: %s", store_name, path, exc)
        return None


def list_blobs_json(store_name: str, prefix: str) -> Optional[list[dict[str, Any]]]:
    """List blobs matching a prefix and decode each as JSON.

    Returns None if Supabase is unavailable (caller should fall back).
    Returns an empty list if the query succeeds but nothing matches.
    """
    client = _get_client()
    if client is None:
        return None
    try:
        res = (
            client.table(_TABLE)
            .select("path, content")
            .eq("store_name", store_name)
            .like("path", f"{prefix}%")
            .execute()
        )
        results: list[dict[str, Any]] = []
        for row in res.data or []:
            raw = row.get("content")
            if raw is None:
                continue
            try:
                results.append(json.loads(base64.b64decode(raw).decode("utf-8")))
            except Exception:
                continue
        return results
    except Exception as exc:
        _log.debug("list_blobs_json(%s, %s) failed: %s", store_name, prefix, exc)
        return None
