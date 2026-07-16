"""Host SaaS provisioning — bind external tenants to mem-dog workspaces.

POST /api/v1/host/bindings — create (or return) org + project + service user + md_* key.
Requires the platform ``API_KEY`` when configured (auth_type=global). In local
dev with no API_KEY, the endpoint is open (same as other admin routes).
"""

from __future__ import annotations

import logging
import re

from fastapi import APIRouter, HTTPException, Query, Request

from app import config
from app.models import (
    APIKeyCreate,
    HostBindingCreate,
    HostBindingResponse,
    OrganizationCreate,
    ProjectCreate,
    UserCreate,
)
from app.storage import get_storage

logger = logging.getLogger("mem_dog.routers.host")

router = APIRouter(prefix="/api/v1/host", tags=["Host SaaS"])


def _require_platform_key(request: Request) -> None:
    """When API_KEY is set, only the global platform key may provision bindings."""
    if not config.API_KEY:
        return
    auth_type = getattr(request.state, "auth_type", None)
    if auth_type != "global":
        raise HTTPException(
            status_code=403,
            detail="Host bindings require the platform API key (x-api-key)",
        )


def _slug(value: str, max_len: int = 40) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", (value or "").strip().lower()).strip("-")
    return (cleaned or "workspace")[:max_len]


@router.post("/bindings", response_model=HostBindingResponse, status_code=201)
async def create_host_binding(body: HostBindingCreate, request: Request) -> HostBindingResponse:
    """Provision org + project + service user + API key for a host workspace.

    Idempotent on ``(external_org_id, external_workspace_id)``. Re-calls return
    the same ids with ``created=false`` and ``api_key=null``.
    """
    _require_platform_key(request)
    storage = get_storage()

    existing = storage.host_binding_get(body.external_org_id, body.external_workspace_id)
    if existing:
        return HostBindingResponse(
            org_id=existing["org_id"],
            project_id=existing["project_id"],
            user_id=existing["user_id"],
            api_key=None,
            created=False,
            external_org_id=body.external_org_id,
            external_workspace_id=body.external_workspace_id,
            display_name=existing.get("display_name") or body.display_name,
        )

    display = (body.display_name or "").strip() or body.external_workspace_id
    org_slug = _slug(f"host-{body.external_org_id}")
    proj_slug = _slug(body.external_workspace_id)
    if len(org_slug) < 2:
        org_slug = f"org-{org_slug}"
    if len(proj_slug) < 2:
        proj_slug = f"ws-{proj_slug}"
    # Username must be unique and meet UserCreate constraints (3–50 chars).
    from ulid import ULID

    ulid = str(ULID())
    username = f"host_{ulid[:16]}".lower()
    email = f"{username}@host.local"

    try:
        user = storage.create_user(
            UserCreate(
                username=username,
                email=email,
                display_name=display,
                metadata={
                    "host_binding": True,
                    "external_org_id": body.external_org_id,
                    "external_workspace_id": body.external_workspace_id,
                    **(body.metadata or {}),
                },
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("host binding: create_user failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    try:
        org = storage.create_organization(
            OrganizationCreate(
                name=org_slug,
                display_name=f"Host {body.external_org_id}",
                metadata={
                    "external_org_id": body.external_org_id,
                    "host_binding": True,
                },
            ),
            owner_user_id=user.user_id,
        )
        project = storage.create_project(
            org.org_id,
            ProjectCreate(
                name=proj_slug,
                display_name=display,
                description="Host SaaS workspace",
                metadata={
                    "external_org_id": body.external_org_id,
                    "external_workspace_id": body.external_workspace_id,
                    "host_binding": True,
                },
            ),
        )
    except Exception as exc:
        logger.exception("host binding: org/project create failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Persist defaults on the service user (best-effort).
    try:
        storage.set_user_defaults(
            user.user_id,
            default_org_id=org.org_id,
            default_project_id=project.project_id,
        )
    except Exception as exc:
        logger.warning("host binding: set_user_defaults failed: %s", exc)

    key_resp = storage.create_api_key(
        user.user_id,
        APIKeyCreate(name="host-workspace"),
    )
    if not key_resp or not key_resp.key:
        raise HTTPException(status_code=500, detail="Failed to create workspace API key")

    record = {
        "org_id": org.org_id,
        "project_id": project.project_id,
        "user_id": user.user_id,
        "external_org_id": body.external_org_id,
        "external_workspace_id": body.external_workspace_id,
        "display_name": display,
        "key_id": key_resp.key_id,
        "metadata": body.metadata or {},
    }
    storage.host_binding_put(record)

    return HostBindingResponse(
        org_id=org.org_id,
        project_id=project.project_id,
        user_id=user.user_id,
        api_key=key_resp.key,
        created=True,
        external_org_id=body.external_org_id,
        external_workspace_id=body.external_workspace_id,
        display_name=display,
    )


@router.get("/bindings", response_model=HostBindingResponse)
async def get_host_binding(
    request: Request,
    external_org_id: str = Query(..., min_length=1),
    external_workspace_id: str = Query(..., min_length=1),
) -> HostBindingResponse:
    """Look up an existing host binding (never returns the raw API key)."""
    _require_platform_key(request)
    storage = get_storage()
    existing = storage.host_binding_get(external_org_id, external_workspace_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Host binding not found")
    return HostBindingResponse(
        org_id=existing["org_id"],
        project_id=existing["project_id"],
        user_id=existing["user_id"],
        api_key=None,
        created=False,
        external_org_id=external_org_id,
        external_workspace_id=external_workspace_id,
        display_name=existing.get("display_name"),
    )
