"""K8s model pod management router.

CREATE / LIST / SCALE / DELETE Ollama model deployments on Kubernetes.
All managed deployments are prefixed with ``mdl-`` and labelled with
``memdog/managed-model=true`` to prevent interference with infrastructure pods.

GET    /api/v1/models/k8s-pods                              — list all
POST   /api/v1/models/k8s-pods                              — create
GET    /api/v1/models/k8s-pods/{name}                       — details
DELETE /api/v1/models/k8s-pods/{name}                       — delete
PATCH  /api/v1/models/k8s-pods/{name}/scale                 — scale 0-3
GET    /api/v1/models/k8s-pods/{name}/logs                  — pod logs
GET    /api/v1/models/k8s-pods/{name}/metrics               — CPU/mem
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.k8s_client import (
    ModelDeploymentSpec,
    ModelDeploymentStatus,
    create_model_deployment,
    delete_model_deployment,
    get_model_deployment,
    get_pod_logs,
    get_pod_metrics,
    is_k8s_available,
    list_model_deployments,
    scale_model_deployment,
)

logger = logging.getLogger("mem_dog.k8s_pods")

router = APIRouter(prefix="/api/v1/models/k8s-pods", tags=["AI Models - K8s Pods"])


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class CreatePodRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=50, pattern=r"^[a-z0-9][a-z0-9-]*$")
    tier: str = Field("small", pattern=r"^(small|medium|large)$")
    models_to_pull: list[str] = Field(default_factory=list)
    replicas: int = Field(1, ge=0, le=3)
    persistent_storage: bool = False
    resource_requests: Optional[dict[str, str]] = None
    resource_limits: Optional[dict[str, str]] = None


class ScaleRequest(BaseModel):
    replicas: int = Field(..., ge=0, le=3)


# ---------------------------------------------------------------------------
# Guard
# ---------------------------------------------------------------------------


def _require_k8s():
    if not is_k8s_available():
        raise HTTPException(
            503, "Kubernetes client not available. Running outside cluster?"
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=list[ModelDeploymentStatus])
async def list_pods():
    """List all managed model deployments."""
    _require_k8s()
    return list_model_deployments()


@router.post("", response_model=ModelDeploymentStatus, status_code=201)
async def create_pod(req: CreatePodRequest):
    """Create a new Ollama model deployment on Kubernetes."""
    _require_k8s()
    spec = ModelDeploymentSpec(
        name=req.name,
        tier=req.tier,
        models_to_pull=req.models_to_pull,
        replicas=req.replicas,
        persistent_storage=req.persistent_storage,
        resource_requests=req.resource_requests,
        resource_limits=req.resource_limits,
    )
    try:
        return create_model_deployment(spec)
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    except Exception as exc:
        logger.exception("Failed to create model deployment")
        raise HTTPException(500, f"Deployment creation failed: {exc}")


@router.get("/{name}", response_model=ModelDeploymentStatus)
async def get_pod(name: str):
    """Get details of a managed model deployment."""
    _require_k8s()
    dep = get_model_deployment(name)
    if not dep:
        raise HTTPException(404, f"Deployment {name} not found")
    return dep


@router.delete("/{name}")
async def remove_pod(name: str):
    """Delete a managed model deployment and its service."""
    _require_k8s()
    try:
        ok = delete_model_deployment(name)
    except ValueError as exc:
        raise HTTPException(403, str(exc))
    if not ok:
        raise HTTPException(404, f"Deployment {name} not found")
    return {"deleted": name}


@router.patch("/{name}/scale", response_model=ModelDeploymentStatus)
async def scale_pod(name: str, req: ScaleRequest):
    """Scale a managed model deployment (0-3 replicas)."""
    _require_k8s()
    try:
        return scale_model_deployment(name, req.replicas)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:
        logger.exception("Failed to scale deployment")
        raise HTTPException(500, f"Scale failed: {exc}")


@router.get("/{name}/logs")
async def pod_logs(name: str, tail: int = 100):
    """Get logs from the first pod of a managed deployment."""
    _require_k8s()
    dep = get_model_deployment(name)
    if not dep:
        raise HTTPException(404, f"Deployment {name} not found")
    logs = get_pod_logs(name, tail=tail)
    return {"name": name, "logs": logs}


@router.get("/{name}/metrics")
async def pod_metrics(name: str):
    """Get CPU/memory usage for pods of a managed deployment."""
    _require_k8s()
    dep = get_model_deployment(name)
    if not dep:
        raise HTTPException(404, f"Deployment {name} not found")
    return get_pod_metrics(name)
