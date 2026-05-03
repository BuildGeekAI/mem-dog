"""Provider-specific HTTP logic for testing connectivity and discovering models.

Each provider has slightly different API shapes for listing models and
validating credentials. This module abstracts those differences behind
two uniform async functions.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from app.provider_registry import get_provider

logger = logging.getLogger("mem_dog.provider_service")

_HTTP_TIMEOUT = 15.0  # seconds


async def test_provider(
    engine_type: str,
    api_key: str | None = None,
    base_url: str | None = None,
) -> dict[str, Any]:
    """Test provider connectivity.

    Returns ``{"ok": True, "latency_ms": int}`` on success, or
    ``{"ok": False, "error": str}`` on failure.
    """
    provider = get_provider(engine_type)
    if not provider:
        return {"ok": False, "error": f"Unknown provider: {engine_type}"}

    url = base_url or provider.default_base_url
    if not url:
        return {"ok": False, "error": "No base URL configured"}

    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            if engine_type == "gemini":
                resp = await _test_gemini(client, url, api_key)
            elif engine_type in ("ollama", "ollama_cloud"):
                resp = await _test_ollama(client, url, api_key)
            elif engine_type == "anthropic":
                resp = await _test_anthropic(client, url, api_key)
            elif engine_type == "bedrock":
                return {"ok": False, "error": "Bedrock requires AWS SDK; test not supported via HTTP"}
            else:
                resp = await _test_openai_compatible(client, url, api_key, provider)

        latency_ms = int((time.monotonic() - t0) * 1000)

        if resp.status_code < 400:
            return {"ok": True, "latency_ms": latency_ms}
        else:
            body = resp.text[:200]
            return {"ok": False, "error": f"HTTP {resp.status_code}: {body}", "latency_ms": latency_ms}

    except httpx.ConnectError as exc:
        return {"ok": False, "error": f"Connection failed: {exc}"}
    except httpx.TimeoutException:
        return {"ok": False, "error": "Request timed out"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def discover_models(
    engine_type: str,
    api_key: str | None = None,
    base_url: str | None = None,
) -> list[str]:
    """Fetch available models from a provider.

    Returns a list of model ID strings. Returns an empty list on error.
    """
    provider = get_provider(engine_type)
    if not provider:
        return []

    url = base_url or provider.default_base_url
    if not url:
        return provider.default_models

    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            if engine_type == "gemini":
                return await _discover_gemini(client, url, api_key)
            elif engine_type in ("ollama", "ollama_cloud"):
                return await _discover_ollama(client, url, api_key)
            elif engine_type == "anthropic":
                return await _discover_anthropic(client, url, api_key)
            elif engine_type == "huggingface":
                return provider.default_models  # HF discovery is too broad
            elif engine_type == "bedrock":
                return provider.default_models  # Requires boto3
            else:
                return await _discover_openai_compatible(client, url, api_key, provider)
    except Exception as exc:
        logger.warning("Model discovery failed for %s: %s", engine_type, exc)
        return provider.default_models


# ---------------------------------------------------------------------------
# Per-provider implementations
# ---------------------------------------------------------------------------

def _auth_headers(api_key: str | None, provider: Any) -> dict[str, str]:
    """Build auth headers from provider config."""
    headers: dict[str, str] = {}
    if api_key and provider.auth_header:
        prefix = f"{provider.auth_scheme} " if provider.auth_scheme else ""
        headers[provider.auth_header] = f"{prefix}{api_key}"
    return headers


# -- OpenAI-compatible (OpenAI, OpenRouter, Together, vLLM, LiteLLM) --

async def _test_openai_compatible(
    client: httpx.AsyncClient, base_url: str, api_key: str | None, provider: Any,
) -> httpx.Response:
    endpoint = provider.models_endpoint or "/models"
    headers = _auth_headers(api_key, provider)
    return await client.get(f"{base_url.rstrip('/')}{endpoint}", headers=headers)


async def _discover_openai_compatible(
    client: httpx.AsyncClient, base_url: str, api_key: str | None, provider: Any,
) -> list[str]:
    endpoint = provider.models_endpoint or "/models"
    headers = _auth_headers(api_key, provider)
    resp = await client.get(f"{base_url.rstrip('/')}{endpoint}", headers=headers)
    resp.raise_for_status()
    data = resp.json()
    items = data.get("data", [])
    return sorted([m["id"] for m in items if isinstance(m, dict) and "id" in m])


# -- Anthropic --

async def _test_anthropic(
    client: httpx.AsyncClient, base_url: str, api_key: str | None,
) -> httpx.Response:
    headers: dict[str, str] = {"anthropic-version": "2023-06-01"}
    if api_key:
        headers["x-api-key"] = api_key
    return await client.get(f"{base_url.rstrip('/')}/v1/models", headers=headers)


async def _discover_anthropic(
    client: httpx.AsyncClient, base_url: str, api_key: str | None,
) -> list[str]:
    headers: dict[str, str] = {"anthropic-version": "2023-06-01"}
    if api_key:
        headers["x-api-key"] = api_key
    resp = await client.get(f"{base_url.rstrip('/')}/v1/models", headers=headers)
    resp.raise_for_status()
    data = resp.json()
    items = data.get("data", [])
    return sorted([m["id"] for m in items if isinstance(m, dict) and "id" in m])


# -- Gemini --

async def _test_gemini(
    client: httpx.AsyncClient, base_url: str, api_key: str | None,
) -> httpx.Response:
    url = f"{base_url.rstrip('/')}/v1beta/models"
    if api_key:
        url += f"?key={api_key}"
    return await client.get(url)


async def _discover_gemini(
    client: httpx.AsyncClient, base_url: str, api_key: str | None,
) -> list[str]:
    url = f"{base_url.rstrip('/')}/v1beta/models"
    if api_key:
        url += f"?key={api_key}"
    resp = await client.get(url)
    resp.raise_for_status()
    data = resp.json()
    models = data.get("models", [])
    return sorted([
        m.get("name", "").replace("models/", "")
        for m in models
        if isinstance(m, dict) and m.get("name")
    ])


# -- Ollama --

async def _test_ollama(
    client: httpx.AsyncClient, base_url: str, api_key: str | None = None,
) -> httpx.Response:
    headers: dict[str, str] = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return await client.get(f"{base_url.rstrip('/')}/api/tags", headers=headers)


async def _discover_ollama(
    client: httpx.AsyncClient, base_url: str, api_key: str | None = None,
) -> list[str]:
    headers: dict[str, str] = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    resp = await client.get(f"{base_url.rstrip('/')}/api/tags", headers=headers)
    resp.raise_for_status()
    data = resp.json()
    models = data.get("models", [])
    return sorted([m.get("name", "") for m in models if isinstance(m, dict) and m.get("name")])
