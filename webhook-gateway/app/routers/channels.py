"""Channel configuration management — proxy to memdog API.

Provides a lightweight facade over the ``/api/v1/channels`` endpoints on
the memdog API so that channel metadata (webhook URLs, auth config) can
be managed directly through the gateway.

GET operations use direct Supabase reads when available (OC-Read pattern),
falling back to the memdog API.  Writes always go through the API.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException

from .. import config
from .. import supabase_reader
from ..channel_policy import list_policies

_log = logging.getLogger("openclaw_gateway.routers.channels")

router = APIRouter(prefix="/channels", tags=["channels"])

_TIMEOUT_S = 15.0

# In Supabase mode the channels store is named "channels" and paths
# are like "{channel_type}/meta.json".
_CHANNELS_STORE = "channels"


async def _proxy_get(path: str) -> Any:
    if not config.MEM_DOG_API_URL:
        raise HTTPException(status_code=503, detail="MEM_DOG_API_URL not configured")
    url = f"{config.MEM_DOG_API_URL}{path}"
    async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
        resp = await client.get(url)
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()


async def _proxy_put(path: str, body: dict[str, Any]) -> Any:
    if not config.MEM_DOG_API_URL:
        raise HTTPException(status_code=503, detail="MEM_DOG_API_URL not configured")
    url = f"{config.MEM_DOG_API_URL}{path}"
    async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
        resp = await client.put(url, json=body)
    if resp.status_code not in (200, 201):
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()


@router.get("")
async def list_channels() -> Any:
    """List all configured channels."""
    result = supabase_reader.list_blobs_json(_CHANNELS_STORE, "")
    if result is not None:
        return [r for r in result if r]
    return await _proxy_get("/api/v1/channels")


@router.get("/policies")
async def get_channel_policies() -> dict[str, Any]:
    """Return the gateway-level channel access policies."""
    return {"policies": list_policies()}


@router.get("/{channel_type}")
async def get_channel(channel_type: str) -> Any:
    """Get configuration for a specific channel type."""
    safe_type = channel_type.replace("/", "_").replace("\\", "_").strip().lower()
    path = f"{safe_type}/meta.json"
    data = supabase_reader.read_blob_json(_CHANNELS_STORE, path)
    if data is not None:
        return data
    return await _proxy_get(f"/api/v1/channels/{channel_type}")


@router.put("/{channel_type}")
async def update_channel(channel_type: str, body: dict[str, Any]) -> Any:
    """Update configuration for a channel type (always via API)."""
    return await _proxy_put(f"/api/v1/channels/{channel_type}", body)
