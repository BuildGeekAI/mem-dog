"""Look up integration credentials for a user via Nango.

Replaces direct Supabase reads with Nango API calls. Falls back to the
mem-dog API when Nango is not available.

Channel affinity tagging logic (tag_connection, _CHANNEL_CATEGORY_AFFINITY,
_CHANNEL_PROVIDER_MATCH) is unchanged — it's pure business logic.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import httpx

from . import config

_log = logging.getLogger("webhook_gateway.credentials")

_CACHE_TTL_S = 300  # 5 minutes
_TIMEOUT_S = 10.0

NANGO_API_URL: str = os.getenv("NANGO_API_URL", "")
NANGO_SECRET_KEY: str = os.getenv("NANGO_SECRET_KEY", "")

# Cache: user_id -> (connections list, timestamp)
_cache: dict[str, tuple[list[dict[str, Any]], float]] = {}


def _nango_headers() -> dict[str, str]:
    h: dict[str, str] = {}
    if NANGO_SECRET_KEY:
        h["Authorization"] = f"Bearer {NANGO_SECRET_KEY}"
    return h


def _try_nango_connections(user_id: str) -> list[dict[str, Any]] | None:
    """Fetch active connections from Nango API (synchronous for cache compatibility)."""
    if not NANGO_API_URL or not NANGO_SECRET_KEY:
        return None
    try:
        resp = httpx.get(
            f"{NANGO_API_URL}/connection",
            params={"end_user": user_id},
            headers=_nango_headers(),
            timeout=_TIMEOUT_S,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        nango_conns = data.get("connections", data) if isinstance(data, dict) else data

        # Map Nango connections to the format tag_connection() expects
        connections = []
        for nc in nango_conns:
            health = nc.get("health", {})
            status = "active"
            if isinstance(health, dict) and health.get("status") == "error":
                status = "error"

            end_user = nc.get("end_user", {})
            uid = end_user.get("id", "") if isinstance(end_user, dict) else ""
            metadata = nc.get("metadata", {}) or {}

            connections.append({
                "connection_id": str(nc.get("connection_id", nc.get("id", ""))),
                "provider_key": nc.get("provider_config_key", nc.get("provider", "")),
                "status": status,
                "account_id": metadata.get("account_id", ""),
                "account_email": metadata.get("account_email", ""),
                "scopes": nc.get("credentials", {}).get("scope") if isinstance(nc.get("credentials"), dict) else "",
                "metadata": metadata,
            })

        return connections
    except Exception as exc:
        _log.debug("Nango connection lookup failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Provider metadata cache — loaded from Nango
# ---------------------------------------------------------------------------
_provider_meta: dict[str, dict[str, str]] | None = None
_provider_meta_ts: float = 0


def _load_provider_meta() -> dict[str, dict[str, Any]]:
    """Load provider_key → metadata mapping from Nango. Cached for 1 hour."""
    global _provider_meta, _provider_meta_ts
    if _provider_meta is not None and time.monotonic() - _provider_meta_ts < 3600:
        return _provider_meta

    if not NANGO_API_URL or not NANGO_SECRET_KEY:
        return _provider_meta or {}

    try:
        resp = httpx.get(
            f"{NANGO_API_URL}/config",
            headers=_nango_headers(),
            timeout=_TIMEOUT_S,
        )
        if resp.status_code != 200:
            return _provider_meta or {}

        data = resp.json()
        configs = data.get("configs", data) if isinstance(data, dict) else data

        _provider_meta = {}
        for cfg in configs:
            key = cfg.get("unique_key", cfg.get("provider_config_key", ""))
            auth_mode_raw = cfg.get("auth_mode", "NONE").upper()
            proxy = cfg.get("proxy", {})
            proxy_base_url = proxy.get("base_url", "") if isinstance(proxy, dict) else ""

            _provider_meta[key] = {
                "category": _get_nango_category(key),
                "auth_mode": auth_mode_raw,
                "proxy_base_url": proxy_base_url,
                "config": cfg.get("custom", {}),
                "token_url": cfg.get("token_url", ""),
            }

        _provider_meta_ts = time.monotonic()
        return _provider_meta
    except Exception as exc:
        _log.debug("Provider meta load failed: %s", exc)
        return _provider_meta or {}


def _get_nango_category(provider_key: str) -> str:
    """Map provider key to app_category (mirrors nango_provider_meta.py)."""
    # Inline the most common mappings for the gateway
    _CATEGORY_MAP = {
        "slack": "communication", "discord": "communication", "telegram": "communication",
        "whatsapp-business": "communication", "microsoft-teams": "communication",
        "gmail": "email", "outlook": "email", "sendgrid": "email",
        "zoom": "video", "google-meet": "video",
        "github": "devtools", "gitlab": "devtools",
        "salesforce": "crm", "hubspot": "crm",
        "stripe": "finance", "shopify": "commerce",
        "zendesk": "support", "openai": "data-ai",
    }
    return _CATEGORY_MAP.get(provider_key, "other")


async def get_provider_meta(provider_key: str) -> dict[str, Any] | None:
    """Get metadata for a single provider. Used by the integration proxy."""
    meta = _load_provider_meta()
    return meta.get(provider_key)


# ---------------------------------------------------------------------------
# Channel-type to provider-category affinity map (unchanged — business logic)
# ---------------------------------------------------------------------------

_CHANNEL_CATEGORY_AFFINITY: dict[str, set[str]] = {
    "slack": {"communication"},
    "discord": {"communication"},
    "telegram": {"communication"},
    "whatsapp": {"communication"},
    "msteams": {"microsoft", "communication"},
    "email": {"email", "google", "microsoft"},
    "webchat": {"communication"},
    "zoom": {"video"},
    "video": {"video"},
    "googlechat": {"google", "communication"},
    "signal": {"communication"},
    "matrix": {"communication"},
    "irc": {"communication"},
    "line": {"communication"},
    "feishu": {"communication"},
    "mattermost": {"communication"},
    "twitch": {"social"},
}

_CHANNEL_PROVIDER_MATCH: dict[str, set[str]] = {
    "slack": {"slack"},
    "discord": {"discord"},
    "telegram": {"telegram"},
    "whatsapp": {"whatsapp-business"},
    "msteams": {"microsoft-teams"},
    "email": {"gmail", "outlook", "sendgrid", "mailgun", "postmark", "mailchimp"},
    "zoom": {"zoom"},
    "googlechat": {"google-meet", "google-calendar"},
    "twitch": {"twitter"},
}


def tag_connection(
    connection: dict[str, Any],
    channel_type: str,
    provider_meta: dict[str, dict[str, str]],
) -> dict[str, Any]:
    """Build a tagged connection reference for envelope injection."""
    provider_key = connection.get("provider_key", "")
    meta = provider_meta.get(provider_key, {})
    category = meta.get("category", "other")
    auth_mode = meta.get("auth_mode", "NONE")

    direct_matches = _CHANNEL_PROVIDER_MATCH.get(channel_type, set())
    affinity_cats = _CHANNEL_CATEGORY_AFFINITY.get(channel_type, set())

    if provider_key in direct_matches:
        relevance = "channel_match"
    elif category in affinity_cats:
        relevance = "category_match"
    else:
        relevance = "available"

    return {
        "provider_key": provider_key,
        "connection_id": connection.get("connection_id", ""),
        "has_credentials": True,
        "tags": {
            "category": category,
            "auth_mode": auth_mode,
            "relevance": relevance,
        },
    }


async def lookup_connections(user_id: str) -> list[dict[str, Any]]:
    """Return ALL active integration connections for a user.

    Tries Nango first, falls back to mem-dog API.
    """
    if not user_id:
        return []

    cached = _cache.get(user_id)
    if cached:
        connections, ts = cached
        if time.monotonic() - ts < _CACHE_TTL_S:
            return connections
        del _cache[user_id]

    # Primary: Nango API
    connections = _try_nango_connections(user_id)
    if connections is not None:
        _cache[user_id] = (connections, time.monotonic())
        return connections

    # Fallback: mem-dog API
    if not config.MEM_DOG_API_URL:
        return []

    url = f"{config.MEM_DOG_API_URL}/api/v1/integrations/connections"
    params: dict[str, str] = {"user_id": user_id}

    try:
        headers: dict[str, str] = {}
        if config.MEM_DOG_API_KEY:
            headers["x-api-key"] = config.MEM_DOG_API_KEY
        async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
            resp = await client.get(url, params=params, headers=headers)
        if resp.status_code == 200:
            connections = resp.json()
            _cache[user_id] = (connections, time.monotonic())
            return connections
    except Exception as exc:
        _log.warning("Connection lookup failed for %s: %s", user_id, exc)

    return []


async def get_credentials(
    user_id: str,
    provider_key: str,
) -> dict[str, Any] | None:
    """Get decrypted credentials for a user + provider.

    Nango auto-refreshes tokens, so returned tokens are always fresh.
    """
    connections = await lookup_connections(user_id)
    matching = [c for c in connections if c.get("provider_key") == provider_key]
    if not matching:
        return None

    connection_id = matching[0].get("connection_id")
    if not connection_id:
        return None

    # Fetch credentials from Nango (includes auto-refreshed tokens)
    if NANGO_API_URL and NANGO_SECRET_KEY:
        try:
            resp = httpx.get(
                f"{NANGO_API_URL}/connection/{connection_id}",
                params={"provider_config_key": provider_key},
                headers=_nango_headers(),
                timeout=_TIMEOUT_S,
            )
            if resp.status_code == 200:
                data = resp.json()
                creds = data.get("credentials", {})
                return {
                    "access_token": creds.get("access_token", ""),
                    "refresh_token": creds.get("refresh_token", ""),
                    "api_key": creds.get("apiKey", creds.get("api_key", "")),
                    "token_type": creds.get("token_type", "bearer"),
                    "expires_at": creds.get("expires_at"),
                }
        except Exception as exc:
            _log.warning("Nango credential fetch failed for %s/%s: %s", user_id, provider_key, exc)

    # Fallback: mem-dog API
    if not config.MEM_DOG_API_URL:
        return None

    url = f"{config.MEM_DOG_API_URL}/api/v1/integrations/connections/{connection_id}/credentials"
    try:
        headers: dict[str, str] = {}
        if config.MEM_DOG_API_KEY:
            headers["x-api-key"] = config.MEM_DOG_API_KEY
        async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
            resp = await client.get(url, headers=headers)
        if resp.status_code == 200:
            return resp.json()
    except Exception as exc:
        _log.warning("Credential fetch failed for %s/%s: %s", user_id, provider_key, exc)

    return None


def clear_cache() -> None:
    """Flush the in-process credentials cache (useful in tests)."""
    _cache.clear()
    global _provider_meta, _provider_meta_ts
    _provider_meta = None
    _provider_meta_ts = 0
