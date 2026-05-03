"""Ollama proxy router — proxy model lifecycle to Ollama on each machine.

GET  /api/v1/models/local-llms/{machine_id}/models              — list models (Ollama /api/tags)
GET  /api/v1/models/local-llms/{machine_id}/models/loaded       — list loaded (Ollama /api/ps)
GET  /api/v1/models/local-llms/{machine_id}/models/{model_name} — model info (Ollama /api/show)
POST /api/v1/models/local-llms/{machine_id}/models/{model_name}/pull   — start pull (async)
GET  /api/v1/models/local-llms/{machine_id}/models/{model_name}/pull-status
POST /api/v1/models/local-llms/{machine_id}/models/{model_name}/unload
POST /api/v1/models/local-llms/{machine_id}/models/copy-from-bucket  — tier only
GET  /api/v1/models/local-llms/{machine_id}/health
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app import config
from app.capacity import check_capacity, get_required_gb
from app.gcp_auth import get_identity_token_for_url
from app.machines_store import Machine, get_machine
from app import model_telemetry

logger = logging.getLogger("mem_dog.ollama_proxy")

router = APIRouter(prefix="/api/v1/models/local-llms", tags=["AI Models - Ollama Proxy"])

# In-memory pull task status: (machine_id, model_name) -> PullTask
_pull_tasks: dict[tuple[str, str], "PullTask"] = {}
_pull_tasks_lock = asyncio.Lock()


@dataclass
class PullTask:
    status: str  # "pulling" | "complete" | "error"
    stage: str = ""
    percent: float = 0
    error: Optional[str] = None


def _resolve_machine(machine_id: str) -> Machine:
    m = get_machine(machine_id)
    if not m:
        raise HTTPException(404, f"Machine {machine_id} not found")
    return m


def _auth_headers(base_url: str) -> dict[str, str]:
    """Headers for Cloud Run private invocation (identity token)."""
    token = get_identity_token_for_url(base_url)
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


async def _ollama_request(machine: Machine, method: str, path: str, **kwargs) -> Any:
    """Make request to Ollama at machine.base_url."""
    url = f"{machine.base_url.rstrip('/')}{path}"
    headers = {**(kwargs.pop("headers", {})), **_auth_headers(machine.base_url)}
    async with httpx.AsyncClient(timeout=300) as client:
        if method == "GET":
            resp = await client.get(url, headers=headers, **kwargs)
        elif method == "POST":
            resp = await client.post(url, headers=headers, **kwargs)
        else:
            raise ValueError(f"Unsupported method {method}")
    resp.raise_for_status()
    if resp.content:
        return resp.json()
    return {}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/{machine_id}/models")
async def list_models(machine_id: str):
    """List models on disk (Ollama /api/tags)."""
    machine = _resolve_machine(machine_id)
    data = await _ollama_request(machine, "GET", "/api/tags")
    return data


@router.get("/{machine_id}/models/loaded")
async def list_loaded(machine_id: str):
    """List models currently in memory (Ollama /api/ps)."""
    machine = _resolve_machine(machine_id)
    data = await _ollama_request(machine, "GET", "/api/ps")
    return data


@router.get("/{machine_id}/models/{model_name:path}")
async def get_model_info(machine_id: str, model_name: str):
    """Model info and capabilities (Ollama /api/show)."""
    machine = _resolve_machine(machine_id)
    data = await _ollama_request(machine, "POST", "/api/show", json={"name": model_name})
    return data


class CopyFromBucketRequest(BaseModel):
    gcs_filename: str = Field(..., min_length=1, max_length=200)


@router.post("/{machine_id}/models/{model_name:path}/pull")
async def pull_model(machine_id: str, model_name: str):
    """Start async pull. Returns 202. Poll pull-status for progress. Capacity check applied."""
    machine = _resolve_machine(machine_id)
    check_capacity(machine, model_name)

    key = (machine_id, model_name)
    async with _pull_tasks_lock:
        if key in _pull_tasks and _pull_tasks[key].status == "pulling":
            raise HTTPException(409, "Pull already in progress for this model")

        _pull_tasks[key] = PullTask(status="pulling", stage="starting")

    import time as _time
    _pull_start = _time.monotonic()

    async def _run_pull():
        nonlocal key
        url = f"{machine.base_url.rstrip('/')}/api/pull"
        headers = _auth_headers(machine.base_url)
        try:
            async with httpx.AsyncClient(timeout=600) as client:
                async with client.stream("POST", url, json={"name": model_name}, headers=headers) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            status = data.get("status", "")
                            completed = data.get("completed", 0)
                            total = data.get("total", 1) or 1
                            percent = (completed / total * 100) if total else 0
                            async with _pull_tasks_lock:
                                _pull_tasks[key] = PullTask(
                                    status="pulling" if status != "success" else "complete",
                                    stage=status,
                                    percent=percent,
                                )
                            if status == "success":
                                break
                        except json.JSONDecodeError:
                            pass
            async with _pull_tasks_lock:
                _pull_tasks[key] = PullTask(status="complete", stage="done", percent=100)
            duration_s = _time.monotonic() - _pull_start
            model_telemetry.record_pull(machine_id, model_name, "complete", duration_s=duration_s)
        except Exception as exc:
            logger.exception("Pull failed for %s on %s", model_name, machine_id)
            async with _pull_tasks_lock:
                _pull_tasks[key] = PullTask(status="error", error=str(exc))
            duration_s = _time.monotonic() - _pull_start
            model_telemetry.record_pull(machine_id, model_name, "error", duration_s=duration_s, error=str(exc))

    asyncio.create_task(_run_pull())
    return {"status": "accepted", "message": "Pull started. Poll pull-status for progress."}


@router.get("/{machine_id}/models/{model_name:path}/pull-status")
async def get_pull_status(machine_id: str, model_name: str):
    """Poll pull progress."""
    key = (machine_id, model_name)
    async with _pull_tasks_lock:
        task = _pull_tasks.get(key)
    if not task:
        return {"status": "unknown"}
    return {
        "status": task.status,
        "stage": task.stage,
        "percent": task.percent,
        "error": task.error,
    }


@router.post("/{machine_id}/models/{model_name:path}/unload")
async def unload_model(machine_id: str, model_name: str):
    """Unload model from memory (Ollama: generate with keep_alive=0)."""
    machine = _resolve_machine(machine_id)
    url = f"{machine.base_url.rstrip('/')}/api/generate"
    headers = _auth_headers(machine.base_url)
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                url,
                json={
                    "model": model_name,
                    "prompt": ".",
                    "stream": False,
                    "keep_alive": 0,
                },
                headers=headers,
            )
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.warning("Unload failed for %s on %s: %s", model_name, machine_id, exc)
        model_telemetry.record_unload(machine_id, model_name, "ERROR")
        raise HTTPException(502, f"Ollama unload failed: {exc.response.text}")
    model_telemetry.record_unload(machine_id, model_name, "OK")
    return {"status": "unloaded"}


@router.post("/{machine_id}/models/copy-from-bucket")
async def copy_from_bucket(machine_id: str, req: CopyFromBucketRequest):
    """Create Ollama model from GCS file (tier only). Capacity check applied."""
    machine = _resolve_machine(machine_id)
    if machine.source != "tier":
        raise HTTPException(400, "copy-from-bucket is only supported for tier machines")

    # For tier with GCS FUSE: path would be /models/{gcs_filename}.gguf or similar
    # This requires the tier container to have GCS mounted. Out of scope for minimal impl.
    # Return 501 for now; implement when GCS FUSE is configured.
    raise HTTPException(501, "copy-from-bucket not yet implemented (requires GCS FUSE on tier)")


@router.get("/{machine_id}/health")
async def machine_health(machine_id: str):
    """Health check (Ollama /api/tags)."""
    machine = _resolve_machine(machine_id)
    try:
        await _ollama_request(machine, "GET", "/api/tags")
        return {"status": "ok"}
    except Exception:
        return {"status": "offline"}
