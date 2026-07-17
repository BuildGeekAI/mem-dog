"""Host SaaS provisioning — create workspaces for external host tenants.

POST /api/v1/host/workspaces — create (or return) org + project + service user + md_* key.
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
    APIKeyResponse,
    HostApiKeyRotateRequest,
    HostApiKeyRotateResponse,
    HostWorkspaceCreate,
    HostWorkspaceExportResponse,
    HostWorkspacePurgeResponse,
    HostWorkspaceResponse,
    OrganizationCreate,
    ProjectCreate,
    UserCreate,
)
from app.storage import get_storage

logger = logging.getLogger("mem_dog.routers.host")

router = APIRouter(prefix="/api/v1/host", tags=["Host SaaS"])


def _require_platform_key(request: Request) -> None:
    """When API_KEY is set, only the global platform key may provision workspaces."""
    if not config.API_KEY:
        return
    auth_type = getattr(request.state, "auth_type", None)
    if auth_type != "global":
        raise HTTPException(
            status_code=403,
            detail="Host workspaces require the platform API key (x-api-key)",
        )


def _slug(value: str, max_len: int = 40) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", (value or "").strip().lower()).strip("-")
    return (cleaned or "workspace")[:max_len]


def _resolve_host_user_id(request: Request, explicit_user_id: str | None = None) -> str:
    """Workspace md_* / JWT → self; platform may pass user_id."""
    auth_type = getattr(request.state, "auth_type", None)
    caller = getattr(request.state, "user_id", None)
    explicit = (explicit_user_id or "").strip() or None

    if auth_type in ("per_user", "jwt"):
        if not caller:
            raise HTTPException(status_code=401, detail="Authentication required")
        if explicit and explicit != caller:
            raise HTTPException(
                status_code=403,
                detail="Cannot manage API keys for another user",
            )
        return caller

    if auth_type == "global":
        if not explicit:
            raise HTTPException(
                status_code=400,
                detail="user_id is required when using the platform API key",
            )
        return explicit

    # Open local (no API_KEY): validate md_* from header if present
    if not config.API_KEY:
        provided = (request.headers.get("x-api-key") or "").strip()
        if provided.startswith("md_"):
            try:
                uid = get_storage().validate_api_key(provided)
            except Exception:
                uid = None
            if uid:
                if explicit and explicit != uid:
                    raise HTTPException(
                        status_code=403,
                        detail="Cannot manage API keys for another user",
                    )
                return uid
        if explicit:
            return explicit
        raise HTTPException(
            status_code=400,
            detail="user_id is required (or pass a workspace md_* x-api-key)",
        )

    raise HTTPException(status_code=401, detail="Authentication required")


@router.post(
    "/workspaces",
    response_model=HostWorkspaceResponse,
    status_code=201,
    openapi_extra={"x-host-saas": True},
)
async def create_host_workspace(
    body: HostWorkspaceCreate, request: Request
) -> HostWorkspaceResponse:
    """Provision org + project + service user + API key for a host workspace.

    Idempotent on ``(external_org_id, external_workspace_id)``. Re-calls return
    the same ids with ``created=false`` and ``api_key=null``.
    """
    _require_platform_key(request)
    storage = get_storage()

    existing = storage.host_workspace_get(body.external_org_id, body.external_workspace_id)
    if existing:
        return HostWorkspaceResponse(
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
                    "host_workspace": True,
                    "external_org_id": body.external_org_id,
                    "external_workspace_id": body.external_workspace_id,
                    **(body.metadata or {}),
                },
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("host workspace: create_user failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    try:
        org = storage.create_organization(
            OrganizationCreate(
                name=org_slug,
                display_name=f"Host {body.external_org_id}",
                metadata={
                    "external_org_id": body.external_org_id,
                    "host_workspace": True,
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
                    "host_workspace": True,
                },
            ),
        )
    except Exception as exc:
        logger.exception("host workspace: org/project create failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Persist defaults on the service user (best-effort).
    try:
        storage.set_user_defaults(
            user.user_id,
            default_org_id=org.org_id,
            default_project_id=project.project_id,
        )
    except Exception as exc:
        logger.warning("host workspace: set_user_defaults failed: %s", exc)

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
    storage.host_workspace_put(record)

    return HostWorkspaceResponse(
        org_id=org.org_id,
        project_id=project.project_id,
        user_id=user.user_id,
        api_key=key_resp.key,
        created=True,
        external_org_id=body.external_org_id,
        external_workspace_id=body.external_workspace_id,
        display_name=display,
    )


@router.get("/workspaces", response_model=HostWorkspaceResponse)
async def get_host_workspace(
    request: Request,
    external_org_id: str = Query(..., min_length=1),
    external_workspace_id: str = Query(..., min_length=1),
) -> HostWorkspaceResponse:
    """Look up an existing host workspace (never returns the raw API key)."""
    _require_platform_key(request)
    storage = get_storage()
    existing = storage.host_workspace_get(external_org_id, external_workspace_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Host workspace not found")
    return HostWorkspaceResponse(
        org_id=existing["org_id"],
        project_id=existing["project_id"],
        user_id=existing["user_id"],
        api_key=None,
        created=False,
        external_org_id=external_org_id,
        external_workspace_id=external_workspace_id,
        display_name=existing.get("display_name"),
    )


async def _purge_nango_connections(user_id: str) -> int:
    """Best-effort delete of Nango connections for a workspace service user."""
    try:
        from app import nango_client
    except Exception:
        return 0
    deleted = 0
    try:
        conns = await nango_client.list_connections(end_user_id=user_id)
    except Exception as exc:
        logger.warning("purge: list Nango connections failed: %s", exc)
        return 0
    for conn in conns or []:
        conn_id = str(conn.get("id") or conn.get("connection_id") or "")
        provider = conn.get("provider_config_key") or conn.get("provider")
        if not conn_id:
            continue
        try:
            await nango_client.delete_connection(conn_id, provider_config_key=provider)
            deleted += 1
        except Exception as exc:
            logger.warning("purge: delete Nango connection %s failed: %s", conn_id, exc)
    return deleted


@router.delete(
    "/workspaces",
    response_model=HostWorkspacePurgeResponse,
    openapi_extra={"x-host-saas": True},
)
async def purge_host_workspace(
    request: Request,
    external_org_id: str = Query(..., min_length=1),
    external_workspace_id: str = Query(..., min_length=1),
    delete_connections: bool = Query(
        False, description="Also delete Nango connections for the workspace user"
    ),
    delete_service_user: bool = Query(
        True, description="Remove the dedicated service user profile after purge"
    ),
) -> HostWorkspacePurgeResponse:
    """Sync purge a host workspace (L0).

    Deletes data (incl. embeddings/viewpoints/parsed artifacts), memories,
    API keys, project/org, host index, and optionally Nango connections.

    Idempotent: if the workspace record is already gone, returns
    ``already_gone=true`` with ``purged=true``.
    """
    _require_platform_key(request)
    storage = get_storage()
    existing = storage.host_workspace_get(external_org_id, external_workspace_id)
    if not existing:
        return HostWorkspacePurgeResponse(
            external_org_id=external_org_id,
            external_workspace_id=external_workspace_id,
            purged=True,
            already_gone=True,
        )

    deleted_connections = 0
    if delete_connections:
        deleted_connections = await _purge_nango_connections(existing["user_id"])

    counts = storage.purge_host_workspace(
        existing, delete_service_user=delete_service_user
    )
    return HostWorkspacePurgeResponse(
        external_org_id=external_org_id,
        external_workspace_id=external_workspace_id,
        org_id=existing.get("org_id"),
        project_id=existing.get("project_id"),
        user_id=existing.get("user_id"),
        deleted_data_count=counts.get("deleted_data_count", 0),
        deleted_memories_count=counts.get("deleted_memories_count", 0),
        deleted_api_keys_count=counts.get("deleted_api_keys_count", 0),
        deleted_connections_count=deleted_connections,
        purged=True,
        already_gone=False,
    )


@router.delete(
    "/workspaces/by-project/{project_id}",
    response_model=HostWorkspacePurgeResponse,
)
async def purge_host_workspace_by_project(
    project_id: str,
    request: Request,
    delete_connections: bool = Query(False),
    delete_service_user: bool = Query(True),
) -> HostWorkspacePurgeResponse:
    """Purge by ``project_id`` (looks up the host workspace index)."""
    _require_platform_key(request)
    storage = get_storage()
    existing = storage.host_workspace_find_by_project_id(project_id)
    if not existing:
        return HostWorkspacePurgeResponse(
            external_org_id="",
            external_workspace_id="",
            project_id=project_id,
            purged=True,
            already_gone=True,
        )
    return await purge_host_workspace(
        request,
        external_org_id=existing["external_org_id"],
        external_workspace_id=existing["external_workspace_id"],
        delete_connections=delete_connections,
        delete_service_user=delete_service_user,
    )


@router.get("/workspaces/export", response_model=HostWorkspaceExportResponse)
async def export_host_workspace(
    request: Request,
    external_org_id: str = Query(..., min_length=1),
    external_workspace_id: str = Query(..., min_length=1),
) -> HostWorkspaceExportResponse:
    """Export a lightweight offboarding manifest (data + memory ids, no blobs)."""
    _require_platform_key(request)
    storage = get_storage()
    existing = storage.host_workspace_get(external_org_id, external_workspace_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Host workspace not found")
    manifest = storage.export_host_workspace_manifest(existing)
    return HostWorkspaceExportResponse(**manifest)


# =============================================================================
# Host API key lifecycle (F5)
# =============================================================================


@router.get("/api-keys", response_model=list[APIKeyResponse])
async def list_host_api_keys(
    request: Request,
    user_id: str | None = Query(None, description="Required for platform key"),
) -> list[APIKeyResponse]:
    """List workspace API keys (never returns raw key material)."""
    target = _resolve_host_user_id(request, user_id)
    storage = get_storage()
    storage._check_user_management_enabled()
    if not storage.get_user(target):
        raise HTTPException(status_code=404, detail=f"User not found: {target}")
    return storage.list_api_keys(target)


@router.post("/api-keys", response_model=APIKeyResponse, status_code=201)
async def create_host_api_key(
    body: APIKeyCreate,
    request: Request,
    user_id: str | None = Query(None, description="Required for platform key"),
) -> APIKeyResponse:
    """Create an additional workspace API key (raw key returned once)."""
    target = _resolve_host_user_id(request, user_id)
    storage = get_storage()
    storage._check_user_management_enabled()
    if not storage.get_user(target):
        raise HTTPException(status_code=404, detail=f"User not found: {target}")
    created = storage.create_api_key(target, body)
    if not created:
        raise HTTPException(status_code=500, detail="Failed to create API key")
    return created


@router.delete("/api-keys/{key_id}")
async def revoke_host_api_key(
    key_id: str,
    request: Request,
    user_id: str | None = Query(None, description="Required for platform key"),
    allow_empty: bool = Query(False),
):
    """Revoke a workspace API key by id."""
    target = _resolve_host_user_id(request, user_id)
    storage = get_storage()
    storage._check_user_management_enabled()
    if not storage.get_user(target):
        raise HTTPException(status_code=404, detail=f"User not found: {target}")
    existing = storage.list_api_keys(target)
    if len(existing) <= 1 and not allow_empty:
        raise HTTPException(
            status_code=400,
            detail="Cannot revoke the last API key; create a replacement first "
            "(or pass allow_empty=true)",
        )
    if not storage.delete_api_key(target, key_id):
        raise HTTPException(status_code=404, detail=f"API key not found: {key_id}")
    return {"message": "API key revoked", "key_id": key_id, "user_id": target}


@router.post(
    "/api-keys/rotate",
    response_model=HostApiKeyRotateResponse,
    openapi_extra={"x-host-saas": True},
)
async def rotate_host_api_key(
    body: HostApiKeyRotateRequest, request: Request
) -> HostApiKeyRotateResponse:
    """Create a new key, then optionally revoke an old one (overlap-friendly).

    Host flow: create → switch clients to new key → call again with
    ``revoke_key_id`` of the old key (or pass revoke on the same call once
    the new key is stored).
    """
    target = _resolve_host_user_id(request, body.user_id)
    storage = get_storage()
    storage._check_user_management_enabled()
    if not storage.get_user(target):
        raise HTTPException(status_code=404, detail=f"User not found: {target}")

    created = storage.create_api_key(
        target,
        APIKeyCreate(name=body.name, expires_in_days=body.expires_in_days),
    )
    if not created or not created.key:
        raise HTTPException(status_code=500, detail="Failed to create API key")

    revoked: str | None = None
    if body.revoke_key_id:
        if body.revoke_key_id == created.key_id:
            raise HTTPException(status_code=400, detail="Cannot revoke the newly created key")
        if not storage.delete_api_key(target, body.revoke_key_id):
            # New key already created — report partial success
            raise HTTPException(
                status_code=404,
                detail=f"New key created ({created.key_id}) but revoke failed: "
                f"key not found: {body.revoke_key_id}",
            )
        revoked = body.revoke_key_id

    return HostApiKeyRotateResponse(
        user_id=target,
        key_id=created.key_id,
        key=created.key,
        key_prefix=created.key_prefix or created.key[:11],
        name=created.name,
        created_at=created.created_at,
        expires_at=created.expires_at,
        revoked_key_id=revoked,
    )
