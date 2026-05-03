"""Read-only proxy to the memdog API.

Forwards GET requests for users, data, memories, embeddings,
channel identities, and stats to the upstream memdog API.
All endpoints are protected by the gateway's existing auth middleware.

Supports ``?pipeline=gke`` on every endpoint to route to the in-cluster
GKE API instead of the default (Cloud Run) API.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Request

from .. import config

_log = logging.getLogger("openclaw_gateway.routers.api_proxy")

router = APIRouter(prefix="/api/v1", tags=["api-proxy"])

_TIMEOUT_S = 15.0


async def _proxy_get(path: str, request: Request) -> Any:
    """Forward a GET request to the memdog API, preserving query params.

    Supports ``?pipeline=gke`` to route to the GKE API instead of Cloud Run.
    The ``pipeline`` param is stripped before forwarding.
    """
    pipeline = request.query_params.get("pipeline")
    base_url = config.get_api_url(pipeline)
    if not base_url:
        raise HTTPException(status_code=503, detail="MEM_DOG_API_URL not configured")
    url = f"{base_url}{path}"
    params = {k: v for k, v in request.query_params.items() if k != "pipeline"}
    async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
        resp = await client.get(url, params=params)
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()


# ── Users ─────────────────────────────────────────────────────────────────

@router.get("/users")
async def list_users(request: Request) -> Any:
    """List all users."""
    return await _proxy_get("/api/v1/users", request)


@router.get("/users/{user_id}")
async def get_user(user_id: str, request: Request) -> Any:
    """Get a specific user by ID."""
    return await _proxy_get(f"/api/v1/users/{user_id}", request)


@router.get("/users/{user_id}/data")
async def get_user_data(user_id: str, request: Request) -> Any:
    """Get all data for a user."""
    return await _proxy_get(f"/api/v1/users/{user_id}/data", request)


# ── Data ──────────────────────────────────────────────────────────────────

@router.get("/data")
async def list_data(request: Request) -> Any:
    """List data items (supports user, skip, limit, tags query params)."""
    return await _proxy_get("/api/v1/data", request)


@router.get("/data/{data_id}")
async def get_data(data_id: str, request: Request) -> Any:
    """Get a specific data item."""
    return await _proxy_get(f"/api/v1/data/{data_id}", request)


@router.get("/data/{data_id}/metadata")
async def get_data_metadata(data_id: str, request: Request) -> Any:
    """Get metadata for a data item."""
    return await _proxy_get(f"/api/v1/data/{data_id}/metadata", request)


@router.get("/data/{data_id}/info")
async def get_data_info(data_id: str, request: Request) -> Any:
    """Get info for a data item."""
    return await _proxy_get(f"/api/v1/data/{data_id}/info", request)


# ── Memories ──────────────────────────────────────────────────────────────

@router.get("/memories")
async def list_memories(request: Request) -> Any:
    """List memories (supports user_id, memory_type, skip, limit query params)."""
    return await _proxy_get("/api/v1/memories", request)


@router.get("/memories/{memory_id}")
async def get_memory(memory_id: str, request: Request) -> Any:
    """Get a specific memory."""
    return await _proxy_get(f"/api/v1/memories/{memory_id}", request)


@router.get("/memories/{memory_id}/data")
async def get_memory_data(memory_id: str, request: Request) -> Any:
    """Get data items linked to a memory."""
    return await _proxy_get(f"/api/v1/memories/{memory_id}/data", request)


@router.get("/memories/{memory_id}/entries")
async def get_memory_entries(memory_id: str, request: Request) -> Any:
    """Get entries for a memory."""
    return await _proxy_get(f"/api/v1/memories/{memory_id}/entries", request)


# ── Embeddings ────────────────────────────────────────────────────────────

@router.get("/ai/embeddings")
async def list_embeddings(request: Request) -> Any:
    """List embeddings (supports data_id, user_id, limit query params)."""
    return await _proxy_get("/api/v1/ai/embeddings", request)


@router.get("/ai/embeddings/{embedding_id}")
async def get_embedding(embedding_id: str, request: Request) -> Any:
    """Get a specific embedding."""
    return await _proxy_get(f"/api/v1/ai/embeddings/{embedding_id}", request)


@router.get("/ai/embeddings/data/{data_id}")
async def get_data_embeddings(data_id: str, request: Request) -> Any:
    """Get embeddings for a specific data item."""
    return await _proxy_get(f"/api/v1/ai/embeddings/data/{data_id}", request)


# ── Channel Identities ───────────────────────────────────────────────────

@router.get("/channel-identities/by-channel")
async def get_identity_by_channel(request: Request) -> Any:
    """Lookup identity by channel_type and channel_unique_id."""
    return await _proxy_get("/api/v1/channel-identities/by-channel", request)


@router.get("/channel-identities/by-user/{user_id}")
async def list_identities_by_user(user_id: str, request: Request) -> Any:
    """List channel identities for a user."""
    return await _proxy_get(f"/api/v1/channel-identities/by-user/{user_id}", request)


# ── Stats ─────────────────────────────────────────────────────────────────

@router.get("/stats")
async def get_stats(request: Request) -> Any:
    """Get global platform stats."""
    return await _proxy_get("/api/v1/stats", request)


@router.get("/stats/data")
async def get_data_stats(request: Request) -> Any:
    """Get data-specific stats."""
    return await _proxy_get("/api/v1/stats/data", request)


@router.get("/stats/memories")
async def get_memory_stats(request: Request) -> Any:
    """Get memory-specific stats."""
    return await _proxy_get("/api/v1/stats/memories", request)


@router.get("/stats/users/{user_id}")
async def get_user_stats(user_id: str, request: Request) -> Any:
    """Get stats for a specific user."""
    return await _proxy_get(f"/api/v1/stats/users/{user_id}", request)
