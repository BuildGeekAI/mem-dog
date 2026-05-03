"""Async HTTP client for the Nango REST API.

Wraps Nango's integration/connection endpoints and provides typed helpers
used by the adapter layer in ``routers/integrations.py``.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger("mem_dog.nango_client")

NANGO_API_URL: str = os.getenv("NANGO_API_URL", "http://nango-server.nango.svc.cluster.local:3003")
NANGO_SECRET_KEY: str = os.getenv("NANGO_SECRET_KEY", "")

_TIMEOUT = 15.0


def _headers() -> dict[str, str]:
    h: dict[str, str] = {"Content-Type": "application/json"}
    if NANGO_SECRET_KEY:
        h["Authorization"] = f"Bearer {NANGO_SECRET_KEY}"
    return h


def is_available() -> bool:
    return bool(NANGO_API_URL and NANGO_SECRET_KEY)


# ---------------------------------------------------------------------------
# Integrations (provider configs)
# ---------------------------------------------------------------------------

async def check_oauth_configured(provider_config_key: str) -> bool:
    """Check if OAuth credentials are set for a provider (Nango hides them from GET)."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        # Try to trigger the OAuth flow — if credentials exist, Nango returns a URL
        # If not, it returns an error. This is a lightweight check.
        resp = await client.get(
            f"{NANGO_API_URL}/config/{provider_config_key}",
            headers=_headers(),
        )
        if resp.status_code != 200:
            return False
        data = resp.json()
        config = data.get("config", data)
        # Nango includes oauth_client_id in some versions, check it
        client_id = config.get("oauth_client_id", "")
        if client_id and client_id not in ("CONFIGURE_ME", "CONFIGURE_VIA_UI"):
            return True
        # If Nango doesn't expose it, we can't tell — assume configured
        # if the provider exists and has been updated recently
        return False


async def list_integrations() -> list[dict[str, Any]]:
    """List all configured integrations (provider configs)."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(f"{NANGO_API_URL}/config", headers=_headers())
        resp.raise_for_status()
        data = resp.json()
        return data.get("configs", data) if isinstance(data, dict) else data


async def get_integration(provider_config_key: str) -> dict[str, Any] | None:
    """Get a single integration by key."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(
            f"{NANGO_API_URL}/config/{provider_config_key}",
            headers=_headers(),
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()


async def create_integration(data: dict[str, Any]) -> dict[str, Any]:
    """Create a new integration."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            f"{NANGO_API_URL}/config",
            json=data,
            headers=_headers(),
        )
        resp.raise_for_status()
        return resp.json()


async def update_integration(provider_config_key: str, data: dict[str, Any]) -> dict[str, Any]:
    """Update an existing integration (Nango PUT /config requires provider + provider_config_key)."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        # Fetch current config to get the provider name
        get_resp = await client.get(
            f"{NANGO_API_URL}/config/{provider_config_key}",
            headers=_headers(),
        )
        get_resp.raise_for_status()
        current = get_resp.json().get("config", get_resp.json())
        provider = current.get("provider", provider_config_key)

        payload = {
            "provider_config_key": provider_config_key,
            "provider": provider,
            **data,
        }
        resp = await client.put(
            f"{NANGO_API_URL}/config",
            json=payload,
            headers=_headers(),
        )
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# Connections
# ---------------------------------------------------------------------------

async def list_connections(end_user_id: str | None = None) -> list[dict[str, Any]]:
    """List connections, optionally filtered by end_user."""
    params: dict[str, str] = {}
    if end_user_id:
        params["end_user"] = end_user_id
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(
            f"{NANGO_API_URL}/connection",
            params=params,
            headers=_headers(),
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("connections", data) if isinstance(data, dict) else data


async def get_connection(
    connection_id: str,
    provider_config_key: str | None = None,
    *,
    include_credentials: bool = False,
) -> dict[str, Any] | None:
    """Get a single connection."""
    params: dict[str, str] = {}
    if provider_config_key:
        params["provider_config_key"] = provider_config_key
    if include_credentials:
        params["force_refresh"] = "false"
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(
            f"{NANGO_API_URL}/connection/{connection_id}",
            params=params,
            headers=_headers(),
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()


async def create_connection(data: dict[str, Any]) -> dict[str, Any]:
    """Create a connection (API key or basic auth)."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            f"{NANGO_API_URL}/connection",
            json=data,
            headers=_headers(),
        )
        resp.raise_for_status()
        return resp.json()


async def delete_connection(
    connection_id: str,
    provider_config_key: str | None = None,
) -> None:
    """Delete a connection."""
    params: dict[str, str] = {}
    if provider_config_key:
        params["provider_config_key"] = provider_config_key
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.delete(
            f"{NANGO_API_URL}/connection/{connection_id}",
            params=params,
            headers=_headers(),
        )
        if resp.status_code not in (200, 204, 404):
            resp.raise_for_status()


# ---------------------------------------------------------------------------
# Connect sessions (OAuth flow)
# ---------------------------------------------------------------------------

async def create_connect_session(
    end_user_id: str,
    provider_config_key: str,
) -> dict[str, Any]:
    """Create a Nango Connect session for OAuth flow.

    Returns ``{"token": "...", "connect_url": "..."}``
    """
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            f"{NANGO_API_URL}/connect/sessions",
            json={
                "end_user": {"id": end_user_id},
                "allowed_integrations": [provider_config_key],
            },
            headers=_headers(),
        )
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# Proxy (credential-injecting)
# ---------------------------------------------------------------------------

async def proxy_request(
    connection_id: str,
    provider_config_key: str,
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
    params: dict[str, str] | None = None,
) -> httpx.Response:
    """Proxy a request through Nango with automatic credential injection."""
    proxy_headers = _headers()
    proxy_headers["Connection-Id"] = connection_id
    proxy_headers["Provider-Config-Key"] = provider_config_key
    if headers:
        proxy_headers.update(headers)

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.request(
            method=method,
            url=f"{NANGO_API_URL}/proxy/{path}",
            headers=proxy_headers,
            content=body,
            params=params,
        )
        return resp
