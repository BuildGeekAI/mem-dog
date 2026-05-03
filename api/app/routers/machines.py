"""Machines router — list, add, remove Ollama hosts.

GET  /api/v1/models/machines         — list all (tier + user-added)
POST /api/v1/models/machines         — add user machine
DELETE /api/v1/models/machines/{id}  — remove user machine only
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

import httpx
from fastapi import APIRouter, HTTPException

LIST_MACHINES_TIMEOUT_S = 20
from pydantic import BaseModel, Field

from app import config
from app.gcp_auth import get_identity_token_for_url
from app.machines_store import Machine, add_machine, build_tier_machines, get_machine, load_machines, remove_machine

logger = logging.getLogger("mem_dog.machines")

router = APIRouter(prefix="/api/v1/models/machines", tags=["AI Models - Machines"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class MachineResponse(BaseModel):
    id: str
    name: str
    base_url: str
    memory_gb: float
    gpu_vram_gb: Optional[float] = None
    source: str  # "tier" | "user"
    health: Optional[str] = None


class AddMachineRequest(BaseModel):
    base_url: str = Field(..., min_length=1, max_length=500)
    name: Optional[str] = Field(None, max_length=100)
    memory_gb: float = Field(8, ge=0.5, le=512)
    gpu_vram_gb: Optional[float] = Field(None, ge=0, le=256)


async def _check_health(base_url: str, timeout: float = 3) -> str:
    """Return 'ok' or 'offline'."""
    try:
        headers = {}
        token = await asyncio.to_thread(get_identity_token_for_url, base_url)
        if token:
            headers["Authorization"] = f"Bearer {token}"
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(f"{base_url.rstrip('/')}/api/tags", headers=headers)
        resp.raise_for_status()
        return "ok"
    except Exception:
        return "offline"


def _machine_to_response(m: Machine, health: Optional[str] = None) -> MachineResponse:
    return MachineResponse(
        id=m.id,
        name=m.name,
        base_url=m.base_url,
        memory_gb=m.memory_gb,
        gpu_vram_gb=m.gpu_vram_gb,
        source=m.source,
        health=health or m.health,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


async def _list_machines_impl(health: bool) -> list[MachineResponse]:
    tier, user = await asyncio.gather(
        asyncio.to_thread(build_tier_machines),
        asyncio.to_thread(load_machines),
    )
    all_machines = tier + user

    if health and all_machines:
        async def check_one(m: Machine) -> tuple[Machine, str]:
            h = await _check_health(m.base_url)
            return (m, h)

        results = await asyncio.gather(
            *[check_one(m) for m in all_machines],
            return_exceptions=True,
        )
        out = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                logger.debug("Health check failed for %s: %s", all_machines[i].id, r)
                out.append(_machine_to_response(all_machines[i], "offline"))
            else:
                m, h = r
                out.append(_machine_to_response(m, h))
        return out

    return [_machine_to_response(m) for m in all_machines]


@router.get("", response_model=list[MachineResponse])
async def list_machines(health: bool = True):
    """List all machines: 4 pre-configured tier + user-added.

    When health=true (default), fetches health from each Ollama instance (best-effort, 3s timeout).
    Tier/user loading runs in thread pool to avoid blocking on GCS.
    """
    try:
        return await asyncio.wait_for(
            _list_machines_impl(health),
            timeout=LIST_MACHINES_TIMEOUT_S,
        )
    except asyncio.TimeoutError:
        logger.warning("list_machines timed out after %ds", LIST_MACHINES_TIMEOUT_S)
        raise HTTPException(504, "Machines list timed out; try again or use ?health=false")


@router.post("", response_model=MachineResponse)
async def create_machine(req: AddMachineRequest):
    """Add a user machine. Validates by calling Ollama /api/tags at base_url."""
    base = req.base_url.strip().rstrip("/")
    if not base.startswith("http://") and not base.startswith("https://"):
        raise HTTPException(400, "base_url must start with http:// or https://")

    health = await _check_health(base)
    if health != "ok":
        raise HTTPException(400, f"Cannot reach Ollama at {base}. Ensure Ollama is running and base_url is correct.")

    machine = add_machine(
        base_url=base,
        name=req.name,
        memory_gb=req.memory_gb,
        gpu_vram_gb=req.gpu_vram_gb,
    )
    return _machine_to_response(machine, "ok")


@router.delete("/{machine_id}")
async def delete_machine(machine_id: str):
    """Remove a user-added machine. Tier machines cannot be removed."""
    if machine_id.startswith("tier:"):
        raise HTTPException(404, "Tier machines cannot be removed")
    ok = remove_machine(machine_id)
    if not ok:
        raise HTTPException(404, "Machine not found")
    return {"deleted": machine_id}
