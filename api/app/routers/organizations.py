"""Organization management router.

Provides CRUD for organizations and org membership.
"""

import logging

from fastapi import APIRouter, HTTPException, Query, Request
from typing import Optional, List

from app.storage import get_storage
from app.models import (
    Organization,
    OrganizationCreate,
    OrganizationUpdate,
    OrgMember,
    OrgMemberAdd,
    OrgMemberUpdate,
    OrgRole,
)
from app import config

logger = logging.getLogger("mem_dog.routers.organizations")

router = APIRouter(prefix="/api/v1/organizations", tags=["Organizations"])


def _resolve_user_id(request: Request) -> str:
    """Extract the authenticated user_id from the request."""
    uid = getattr(request.state, "user_id", None)
    return uid or config.DEFAULT_USER_ID


# =========================================================================
# Organization CRUD
# =========================================================================


@router.post("", response_model=Organization, status_code=201)
async def create_organization(body: OrganizationCreate, request: Request):
    """Create a new organization. The caller becomes the owner."""
    storage = get_storage()
    caller = _resolve_user_id(request)
    try:
        org = storage.create_organization(body, owner_user_id=caller)
        return org
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.exception("Failed to create organization")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
async def list_organizations(request: Request):
    """List organizations the caller belongs to."""
    storage = get_storage()
    caller = _resolve_user_id(request)
    try:
        orgs = storage.list_organizations(user_id=caller)
        return {"organizations": [o.model_dump() for o in orgs], "total": len(orgs)}
    except Exception as e:
        logger.exception("Failed to list organizations")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{org_id}", response_model=Organization)
async def get_organization(org_id: str):
    """Get organization details."""
    storage = get_storage()
    try:
        org = storage.get_organization(org_id)
        if not org:
            raise HTTPException(status_code=404, detail=f"Organization not found: {org_id}")
        return org
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get organization")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{org_id}", response_model=Organization)
async def update_organization(org_id: str, body: OrganizationUpdate, request: Request):
    """Update an organization (owner/admin only)."""
    storage = get_storage()
    caller = _resolve_user_id(request)
    try:
        org = storage.get_organization(org_id)
        if not org:
            raise HTTPException(status_code=404, detail=f"Organization not found: {org_id}")
        _require_org_role(storage, org_id, caller, {OrgRole.OWNER, OrgRole.ADMIN})
        updated = storage.update_organization(org_id, body)
        return updated
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to update organization")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{org_id}")
async def delete_organization(org_id: str, request: Request):
    """Delete an organization (owner only)."""
    storage = get_storage()
    caller = _resolve_user_id(request)
    try:
        org = storage.get_organization(org_id)
        if not org:
            raise HTTPException(status_code=404, detail=f"Organization not found: {org_id}")
        _require_org_role(storage, org_id, caller, {OrgRole.OWNER})
        storage.delete_organization(org_id)
        return {"org_id": org_id, "deleted": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to delete organization")
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================================
# Membership
# =========================================================================


def _require_org_role(storage, org_id: str, user_id: str, allowed_roles: set):
    """Raise 403 if user doesn't hold one of the allowed roles."""
    member = storage.get_org_member(org_id, user_id)
    if not member or OrgRole(member.role) not in allowed_roles:
        raise HTTPException(status_code=403, detail="Insufficient permissions")


@router.post("/{org_id}/members", response_model=OrgMember, status_code=201)
async def add_member(org_id: str, body: OrgMemberAdd, request: Request):
    """Add a member to the organization (owner/admin only)."""
    storage = get_storage()
    caller = _resolve_user_id(request)
    try:
        org = storage.get_organization(org_id)
        if not org:
            raise HTTPException(status_code=404, detail=f"Organization not found: {org_id}")
        _require_org_role(storage, org_id, caller, {OrgRole.OWNER, OrgRole.ADMIN})
        member = storage.add_org_member(org_id, body.user_id, body.role)
        return member
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.exception("Failed to add member")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{org_id}/members")
async def list_members(org_id: str, request: Request):
    """List members of an organization (must be a member to view)."""
    storage = get_storage()
    caller = _resolve_user_id(request)
    try:
        # Only members of the org can list its members
        caller_member = storage.get_org_member(org_id, caller)
        if not caller_member:
            raise HTTPException(status_code=403, detail="Not a member of this organization")
        members = storage.list_org_members(org_id)
        return {"members": [m.model_dump() for m in members], "total": len(members)}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to list members")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{org_id}/members/{user_id}", response_model=OrgMember)
async def update_member_role(org_id: str, user_id: str, body: OrgMemberUpdate, request: Request):
    """Change a member's role (owner/admin only)."""
    storage = get_storage()
    caller = _resolve_user_id(request)
    try:
        _require_org_role(storage, org_id, caller, {OrgRole.OWNER, OrgRole.ADMIN})
        member = storage.update_org_member_role(org_id, user_id, body.role)
        if not member:
            raise HTTPException(status_code=404, detail="Member not found")
        return member
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to update member role")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{org_id}/members/{user_id}")
async def remove_member(org_id: str, user_id: str, request: Request):
    """Remove a member from the organization (owner/admin only)."""
    storage = get_storage()
    caller = _resolve_user_id(request)
    try:
        _require_org_role(storage, org_id, caller, {OrgRole.OWNER, OrgRole.ADMIN})
        storage.remove_org_member(org_id, user_id)
        return {"org_id": org_id, "user_id": user_id, "removed": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to remove member")
        raise HTTPException(status_code=500, detail=str(e))
