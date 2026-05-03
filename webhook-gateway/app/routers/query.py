"""Query pass-through to the memdog API.

Provides a convenience endpoint for OpenClaw and UI access. Resolves
user_id from channel identity when x-channel-type and x-peer-id headers
are provided, enabling multi-user data isolation through a single
OpenClaw instance.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Request

from .. import config
from ..identity import resolve_user_id

_log = logging.getLogger("openclaw_gateway.routers.query")

router = APIRouter(prefix="/query", tags=["query"])

_TIMEOUT_S = 60.0


def _api_headers() -> dict[str, str]:
    """Build headers for forwarding to the memdog API."""
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if config.MEM_DOG_API_KEY:
        headers["x-api-key"] = config.MEM_DOG_API_KEY
    return headers


async def _resolve_user(request: Request, body: dict[str, Any]) -> str:
    """Resolve user_id from request headers, body, or channel identity.

    Priority:
    1. x-user-id header (explicit)
    2. user_id in request body
    3. Channel identity lookup (x-channel-type + x-peer-id headers)
    4. DEFAULT_USER_ID fallback
    """
    # Explicit user_id
    user_id = request.headers.get("x-user-id", "")
    if user_id:
        return user_id

    # From body
    user_id = body.get("user_id", body.get("user", ""))
    if user_id:
        return user_id

    # Channel identity resolution
    channel_type = request.headers.get("x-channel-type", "")
    peer_id = request.headers.get("x-peer-id", "")
    if channel_type and peer_id:
        resolved = await resolve_user_id(channel_type, peer_id)
        if resolved:
            return resolved

    return config.DEFAULT_USER_ID


@router.post("")
async def query(request: Request, body: dict[str, Any]) -> Any:
    """Forward a query to the memdog AI query endpoint.

    Supports multi-user via:
    - x-user-id header
    - x-channel-type + x-peer-id headers (channel identity lookup)
    - user_id in body
    """
    if not config.MEM_DOG_API_URL:
        raise HTTPException(status_code=503, detail="MEM_DOG_API_URL not configured")

    user_id = await _resolve_user(request, body)
    body["user_id"] = user_id

    url = f"{config.MEM_DOG_API_URL}/api/v1/ai/query"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
            resp = await client.post(url, json=body, headers=_api_headers())
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        return resp.json()
    except httpx.HTTPError as exc:
        _log.error("Query proxy failed: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/search")
async def search(request: Request, body: dict[str, Any]) -> Any:
    """Forward a semantic search to the memdog API."""
    if not config.MEM_DOG_API_URL:
        raise HTTPException(status_code=503, detail="MEM_DOG_API_URL not configured")

    user_id = await _resolve_user(request, body)
    body["user_id"] = user_id

    url = f"{config.MEM_DOG_API_URL}/api/v1/ai/query/semantic"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
            resp = await client.post(url, json=body, headers=_api_headers())
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        return resp.json()
    except httpx.HTTPError as exc:
        _log.error("Search proxy failed: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/chat")
async def chat(request: Request, body: dict[str, Any]) -> Any:
    """Forward a RAG chat query to the memdog API."""
    if not config.MEM_DOG_API_URL:
        raise HTTPException(status_code=503, detail="MEM_DOG_API_URL not configured")

    user_id = await _resolve_user(request, body)
    body["user_id"] = user_id

    url = f"{config.MEM_DOG_API_URL}/api/v1/ai/query/chat"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
            resp = await client.post(url, json=body, headers=_api_headers())
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        return resp.json()
    except httpx.HTTPError as exc:
        _log.error("Chat proxy failed: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/ingest")
async def ingest(request: Request, body: dict[str, Any]) -> Any:
    """Forward data ingestion to the memdog API, scoped to resolved user."""
    if not config.MEM_DOG_API_URL:
        raise HTTPException(status_code=503, detail="MEM_DOG_API_URL not configured")

    user_id = await _resolve_user(request, body)

    url = f"{config.MEM_DOG_API_URL}/api/v1/data"
    # Add user scoping
    headers = _api_headers()
    headers["x-user-id"] = user_id

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
            resp = await client.post(url, json=body, headers=headers)
        if resp.status_code not in (200, 201):
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        return resp.json()
    except httpx.HTTPError as exc:
        _log.error("Ingest proxy failed: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc))
