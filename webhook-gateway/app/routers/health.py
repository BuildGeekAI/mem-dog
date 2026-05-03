"""Health and readiness endpoints."""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter

from .. import config
from ..llm import get_provider_info

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, Any]:
    """Shallow liveness check."""
    return {"status": "ok", "service": "webhook-gateway"}


@router.get("/ready")
async def ready() -> dict[str, Any]:
    """Deep readiness check -- verifies downstream dependencies."""
    checks: dict[str, str] = {}

    if config.MEM_DOG_API_URL:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{config.MEM_DOG_API_URL}/health")
            checks["mem_dog_api"] = "ok" if resp.status_code == 200 else f"HTTP {resp.status_code}"
        except Exception as exc:
            checks["mem_dog_api"] = f"error: {exc}"
    else:
        checks["mem_dog_api"] = "not_configured"

    provider_info = get_provider_info()
    checks["llm_provider"] = provider_info["provider"]
    checks["llm_model"] = provider_info["model"]
    checks["llm"] = "configured" if provider_info["configured"] else "not_configured"
    checks["webhook_gateway"] = "configured" if config.WEBHOOK_GATEWAY_URL else "not_configured"

    all_ok = all(
        v in ("ok", "configured") or k in ("llm_provider", "llm_model")
        for k, v in checks.items()
    )
    return {
        "status": "ready" if all_ok else "degraded",
        "service": "webhook-gateway",
        "checks": checks,
    }
