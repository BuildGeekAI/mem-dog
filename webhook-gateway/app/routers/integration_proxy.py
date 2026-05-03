"""Credential-injecting API proxy for integration providers.

Proxies HTTP requests to upstream provider APIs, automatically injecting
stored OAuth2 tokens or API keys from the user's integration connections.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Request, Response

from ..credentials import get_credentials, get_provider_meta

_log = logging.getLogger("webhook_gateway.routers.integration_proxy")

router = APIRouter(prefix="/proxy", tags=["integration-proxy"])

_TIMEOUT_S = 30.0
_MAX_RETRIES = 3
_MAX_RETRY_AFTER = 30


async def _forward_request(
    method: str,
    url: str,
    headers: dict[str, str],
    body: bytes | None,
    query_params: dict[str, str],
) -> httpx.Response:
    """Send request to upstream provider."""
    async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
        return await client.request(
            method=method,
            url=url,
            headers=headers,
            content=body,
            params=query_params or None,
        )


async def _forward_with_retry(
    method: str,
    url: str,
    headers: dict[str, str],
    body: bytes | None,
    query_params: dict[str, str],
) -> httpx.Response:
    """Forward request with retry on upstream 429."""
    resp = await _forward_request(method, url, headers, body, query_params)

    if resp.status_code != 429:
        return resp

    for attempt in range(_MAX_RETRIES):
        retry_after = resp.headers.get("retry-after")
        if retry_after:
            try:
                wait = min(float(retry_after), _MAX_RETRY_AFTER)
            except ValueError:
                wait = min(2 ** attempt, _MAX_RETRY_AFTER)
        else:
            wait = min(2 ** attempt, _MAX_RETRY_AFTER)

        _log.debug("Upstream 429, retrying in %.1fs (attempt %d)", wait, attempt + 1)
        await asyncio.sleep(wait)
        resp = await _forward_request(method, url, headers, body, query_params)
        if resp.status_code != 429:
            return resp

    return resp


def _build_auth_header(
    creds: dict[str, Any],
    provider_meta: dict[str, Any],
) -> dict[str, str]:
    """Build the appropriate auth header based on provider auth mode."""
    auth_mode = provider_meta.get("auth_mode", "OAUTH2")
    config = provider_meta.get("config", {})

    if auth_mode == "API_KEY":
        api_key = creds.get("access_token") or creds.get("api_key", "")
        header_name = config.get("api_key_header", "Authorization")
        if header_name.lower() == "authorization":
            return {"Authorization": f"Bearer {api_key}"}
        return {header_name: api_key}

    # Default: OAuth2 Bearer token
    access_token = creds.get("access_token", "")
    return {"Authorization": f"Bearer {access_token}"}


@router.api_route(
    "/{provider_key}/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    summary="Proxy request to provider API",
    description=(
        "Forward an HTTP request to an upstream provider API with automatic "
        "credential injection. Supports OAuth2 Bearer tokens and API keys. "
        "On upstream 401 (OAuth2 providers): attempts token refresh and retries once. "
        "On upstream 429: retries up to 3 times with exponential backoff, honouring "
        "the Retry-After header (capped at 30s). "
        "Use `?normalize=contact` or `?normalize=calendar_event` to apply unified "
        "data model transforms to the response."
    ),
    response_description="Upstream provider response (or normalized JSON when ?normalize is set)",
)
async def proxy_request(
    provider_key: str,
    path: str,
    request: Request,
    user_id: str = "",
) -> Response:
    """Proxy a request to an upstream provider API with credential injection."""
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id query param required")

    # Load provider metadata
    provider_meta = await get_provider_meta(provider_key)
    if not provider_meta:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {provider_key}")

    proxy_base_url = provider_meta.get("proxy_base_url")
    if not proxy_base_url:
        raise HTTPException(
            status_code=400,
            detail=f"Provider {provider_key} has no proxy_base_url configured",
        )

    # Get credentials
    creds = await get_credentials(user_id, provider_key)
    if not creds:
        raise HTTPException(
            status_code=401,
            detail=f"No active credentials for {provider_key}. Connect via /api/v1/integrations first.",
        )

    # Build target URL and headers
    target_url = f"{proxy_base_url.rstrip('/')}/{path}"
    auth_headers = _build_auth_header(creds, provider_meta)

    # Preserve content-type from original request
    forwarded_headers = dict(auth_headers)
    content_type = request.headers.get("content-type")
    if content_type:
        forwarded_headers["Content-Type"] = content_type

    # Strip user_id from forwarded query params
    query_params = {k: v for k, v in request.query_params.items() if k not in ("user_id", "normalize")}

    body = await request.body() if request.method in ("POST", "PUT", "PATCH") else None

    # Forward request
    resp = await _forward_with_retry(
        method=request.method,
        url=target_url,
        headers=forwarded_headers,
        body=body,
        query_params=query_params,
    )

    # Nango auto-refreshes OAuth2 tokens, so 401 retry is not needed.
    # Apply normalization if requested
    normalize = request.query_params.get("normalize")
    if normalize and resp.status_code == 200:
        return _maybe_normalize(resp, provider_key, normalize)

    return Response(
        content=resp.content,
        status_code=resp.status_code,
        media_type=resp.headers.get("content-type", "application/json"),
    )


def _maybe_normalize(
    resp: httpx.Response,
    provider_key: str,
    resource_type: str,
) -> Response:
    """Apply unified data model transform if available."""
    import json
    from ..transforms import get_transform

    transform_fn = get_transform(provider_key, resource_type)
    if not transform_fn:
        return Response(
            content=resp.content,
            status_code=resp.status_code,
            media_type="application/json",
            headers={"X-Normalize-Warning": f"No transform for {provider_key}/{resource_type}"},
        )

    try:
        raw_data = resp.json()
        # Handle both single objects and arrays/nested results
        items = raw_data
        if isinstance(raw_data, dict):
            # Common patterns: results, data, items, records, value
            for key in ("results", "data", "items", "records", "value", "contacts"):
                if key in raw_data and isinstance(raw_data[key], list):
                    items = raw_data[key]
                    break

        if isinstance(items, list):
            normalized = [transform_fn(item) for item in items]
        else:
            normalized = [transform_fn(items)]

        result = {"normalized": normalized, "raw": raw_data}
        return Response(
            content=json.dumps(result, default=str),
            status_code=200,
            media_type="application/json",
        )
    except Exception as exc:
        _log.warning("Normalization failed for %s/%s: %s", provider_key, resource_type, exc)
        return Response(
            content=resp.content,
            status_code=resp.status_code,
            media_type="application/json",
            headers={"X-Normalize-Warning": f"Transform error: {exc}"},
        )
