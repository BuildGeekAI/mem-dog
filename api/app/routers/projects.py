"""Project management router.

Provides CRUD for projects within organizations.
"""

import logging

from fastapi import APIRouter, HTTPException, Request

from app.storage import get_storage
from app.models import (
    Project,
    ProjectCreate,
    ProjectUpdate,
    OrgRole,
)
from app import config

logger = logging.getLogger("mem_dog.routers.projects")

router = APIRouter(tags=["Projects"])


def _resolve_user_id(request: Request) -> str:
    uid = getattr(request.state, "user_id", None)
    return uid or config.DEFAULT_USER_ID


def _require_org_member(storage, org_id: str, user_id: str):
    """Raise 403 if user is not a member of the org."""
    member = storage.get_org_member(org_id, user_id)
    if not member:
        raise HTTPException(status_code=403, detail="Not a member of this organization")


def _require_org_write(storage, org_id: str, user_id: str):
    """Raise 403 if user doesn't have write access (owner/admin/member)."""
    member = storage.get_org_member(org_id, user_id)
    if not member or OrgRole(member.role) == OrgRole.VIEWER:
        raise HTTPException(status_code=403, detail="Insufficient permissions")


# =========================================================================
# Project CRUD (nested under org)
# =========================================================================


@router.post("/api/v1/organizations/{org_id}/projects", response_model=Project, status_code=201)
async def create_project(org_id: str, body: ProjectCreate, request: Request):
    """Create a project within an organization."""
    storage = get_storage()
    caller = _resolve_user_id(request)
    try:
        org = storage.get_organization(org_id)
        if not org:
            raise HTTPException(status_code=404, detail=f"Organization not found: {org_id}")
        _require_org_write(storage, org_id, caller)
        project = storage.create_project(org_id, body)
        return project
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.exception("Failed to create project")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/v1/organizations/{org_id}/projects")
async def list_projects(org_id: str, request: Request):
    """List projects in an organization."""
    storage = get_storage()
    caller = _resolve_user_id(request)
    try:
        org = storage.get_organization(org_id)
        if not org:
            raise HTTPException(status_code=404, detail=f"Organization not found: {org_id}")
        _require_org_member(storage, org_id, caller)
        projects = storage.list_projects(org_id)
        return {"projects": [p.model_dump() for p in projects], "total": len(projects)}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to list projects")
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================================
# Direct project access by ID
# =========================================================================


@router.get("/api/v1/projects/{project_id}", response_model=Project)
async def get_project(project_id: str):
    """Get a project by ID."""
    storage = get_storage()
    try:
        project = storage.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")
        return project
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get project")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/api/v1/projects/{project_id}", response_model=Project)
async def update_project(project_id: str, body: ProjectUpdate, request: Request):
    """Update a project."""
    storage = get_storage()
    caller = _resolve_user_id(request)
    try:
        project = storage.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")
        _require_org_write(storage, project.org_id, caller)
        updated = storage.update_project(project_id, body)
        return updated
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to update project")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/v1/projects/{project_id}")
async def delete_project(project_id: str, request: Request):
    """Delete a project."""
    storage = get_storage()
    caller = _resolve_user_id(request)
    try:
        project = storage.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")
        _require_org_write(storage, project.org_id, caller)
        storage.delete_project(project_id)
        return {"project_id": project_id, "deleted": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to delete project")
        raise HTTPException(status_code=500, detail=str(e))
