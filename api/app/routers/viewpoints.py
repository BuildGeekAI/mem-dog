from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional

from app import config
from app.storage import get_storage
from app.models import Viewpoint, ViewpointCreate, ViewpointUpdate, ViewpointResponse

router = APIRouter(prefix="/api/v1/ai/viewpoints", tags=["AI Viewpoints"])


class BulkDeleteViewpointsRequest(BaseModel):
    viewpoint_ids: List[str]


@router.get("")
async def list_viewpoints(
    data_id: Optional[str] = Query(default=None, description="Filter by data ID"),
    user_id: str = Query(default="", description="Owner user ID (scopes the search to this user's data)"),
    limit: int = Query(default=50, le=100),
):
    """List viewpoints with optional filtering.

    Viewpoints are AI-generated interpretations and analyses of data.
    """
    try:
        storage = get_storage()
        storage._check_ai_enabled()
        owner = user_id.strip() or config.DEFAULT_USER_ID
        viewpoints = storage.list_viewpoints(data_id=data_id, user_id=owner)
        return {"viewpoints": viewpoints[:limit], "total": len(viewpoints[:limit])}
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=ViewpointResponse, status_code=201)
async def create_viewpoint(viewpoint_create: ViewpointCreate):
    """Create a new AI viewpoint for data.

    A viewpoint includes:
    - AI-generated analysis/interpretation
    - Prompt used for generation
    - AI signature tracking provenance
    - Version history support

    Set ``user_id`` in the request body to store under the correct multitenant path.
    """
    try:
        storage = get_storage()
        storage._check_ai_enabled()
        if not viewpoint_create.user_id.strip():
            viewpoint_create.user_id = config.DEFAULT_USER_ID
        viewpoint = storage.create_viewpoint(viewpoint_create)
        if not viewpoint:
            raise HTTPException(status_code=500, detail="Failed to create viewpoint")
        return viewpoint
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Static path routes MUST come before catch-all /{viewpoint_id} ---

@router.post("/bulk-delete")
async def bulk_delete_viewpoints(
    request: BulkDeleteViewpointsRequest,
    user_id: str = Query(default="", description="Owner user ID"),
):
    """Delete multiple viewpoints by their IDs."""
    try:
        storage = get_storage()
        storage._check_ai_enabled()
        owner = user_id.strip() or config.DEFAULT_USER_ID
        deleted = []
        failed = []
        for vid in request.viewpoint_ids:
            try:
                success = storage.delete_viewpoint(vid, user_id=owner)
                if success:
                    deleted.append(vid)
                else:
                    failed.append(vid)
            except Exception:
                failed.append(vid)
        return {
            "deleted_count": len(deleted),
            "failed_count": len(failed),
            "deleted_ids": deleted,
            "failed_ids": failed,
        }
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/data/{data_id}")
async def get_data_viewpoints(
    data_id: str,
    user_id: str = Query(default="", description="Owner user ID"),
):
    """Get all viewpoints for a specific data item."""
    try:
        storage = get_storage()
        storage._check_ai_enabled()
        owner = user_id.strip() or config.DEFAULT_USER_ID
        viewpoints = storage.list_viewpoints(data_id=data_id, user_id=owner)
        return {"data_id": data_id, "viewpoints": viewpoints, "total": len(viewpoints)}
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Catch-all /{viewpoint_id} routes (must be last) ---

@router.get("/{viewpoint_id}", response_model=ViewpointResponse)
async def get_viewpoint(
    viewpoint_id: str,
    user_id: str = Query(default="", description="Owner user ID (improves lookup performance)"),
):
    """Get a specific viewpoint by ID."""
    storage = get_storage()
    storage._check_ai_enabled()

    try:
        owner = user_id.strip() or config.DEFAULT_USER_ID
        viewpoint = storage.get_viewpoint(viewpoint_id, user_id=owner)
        if not viewpoint:
            raise HTTPException(status_code=404, detail=f"Viewpoint not found: {viewpoint_id}")
        return viewpoint
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{viewpoint_id}", response_model=ViewpointResponse)
async def update_viewpoint(
    viewpoint_id: str,
    viewpoint_update: ViewpointUpdate,
    user_id: str = Query(default="", description="Owner user ID"),
):
    """Update a viewpoint (creates a new version).

    Previous versions are preserved for history tracking.
    """
    try:
        storage = get_storage()
        storage._check_ai_enabled()
        owner = user_id.strip() or config.DEFAULT_USER_ID
        viewpoint = storage.update_viewpoint(viewpoint_id, viewpoint_update, user_id=owner)
        if not viewpoint:
            raise HTTPException(status_code=404, detail=f"Viewpoint not found: {viewpoint_id}")
        return viewpoint
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{viewpoint_id}")
async def delete_viewpoint(
    viewpoint_id: str,
    user_id: str = Query(default="", description="Owner user ID (scopes deletion to this user)"),
):
    """Delete a viewpoint."""
    try:
        storage = get_storage()
        storage._check_ai_enabled()
        owner = user_id.strip() or config.DEFAULT_USER_ID
        success = storage.delete_viewpoint(viewpoint_id, user_id=owner)
        if not success:
            raise HTTPException(status_code=404, detail=f"Viewpoint not found: {viewpoint_id}")
        return {"message": "Viewpoint deleted", "viewpoint_id": viewpoint_id}
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{viewpoint_id}/history")
async def get_viewpoint_history(
    viewpoint_id: str,
    user_id: str = Query(default="", description="Owner user ID"),
):
    """Get version history for a viewpoint."""
    try:
        storage = get_storage()
        storage._check_ai_enabled()
        owner = user_id.strip() or config.DEFAULT_USER_ID
        viewpoint = storage.get_viewpoint(viewpoint_id, user_id=owner)
        if not viewpoint:
            raise HTTPException(status_code=404, detail=f"Viewpoint not found: {viewpoint_id}")

        return {
            "viewpoint_id": viewpoint_id,
            "current_version": viewpoint.version,
            "version_history": viewpoint.version_history or [],
        }
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
