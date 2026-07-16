import logging
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel

from app import config
from app.models import (
    APIKeyCreate,
    APIKeyResponse,
    Memory,
    Prompt,
    Skill,
    User,
    UserCreate,
    UsersListResponse,
    UserResponse,
    UserUpdate,
    DataListItem,
)
from app.models import CreateDataResponse
from app.routers.data import _create_data_impl
from app.storage import get_storage

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/users", tags=["Users"])


def _require_self_or_platform(request: Request, user_id: str) -> None:
    """md_*/JWT may only manage their own keys; platform key may manage any."""
    if not config.API_KEY:
        return
    auth_type = getattr(request.state, "auth_type", None)
    caller = getattr(request.state, "user_id", None)
    if auth_type == "global":
        return
    if auth_type in ("per_user", "jwt") and caller and caller == user_id:
        return
    raise HTTPException(
        status_code=403,
        detail="API keys can only be managed by the key owner or platform API key",
    )


class UserAllDataResponse(BaseModel):
    """All data owned by a single user (from blob storage)."""

    user: UserResponse
    memories: List[Memory]
    prompts: List[Prompt]
    skills: List[Skill]
    memory_count: int
    prompt_count: int
    skill_count: int


class BulkDataCounts(BaseModel):
    users: int
    memories: int
    data_items: int
    prompts: int
    skills: int


class BulkUserDataDump(BaseModel):
    """Full dump of all user-owned data from blob storage."""

    users: List[UserResponse]
    memories: List[Memory]
    data_items: List[DataListItem]
    prompts: List[Prompt]
    skills: List[Skill]
    counts: BulkDataCounts


@router.get("/dump", response_model=BulkUserDataDump)
async def dump_all_user_data():
    """Dump every user-owned row in a single response.

    Returns all users, memories, data items, prompts, and skills from blob storage.
    Intended for admin/debugging use — no pagination, returns everything.
    """
    storage = get_storage()
    storage._check_user_management_enabled()

    try:
        users, _ = storage.list_users(limit=100_000)
        memories, _ = storage.list_memories(limit=100_000)
        data_items = storage.list_all_metadata()
        prompts = storage.list_all_prompts()
        skills = storage.list_all_skills()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Dump failed: {exc}")

    return BulkUserDataDump(
        users=[UserResponse(**u.model_dump()) for u in users],
        memories=memories,
        data_items=data_items,
        prompts=prompts,
        skills=skills,
        counts=BulkDataCounts(
            users=len(users),
            memories=len(memories),
            data_items=len(data_items),
            prompts=len(prompts),
            skills=len(skills),
        ),
    )


@router.get("", response_model=UsersListResponse)
async def list_users(
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0)
):
    """List all users with pagination."""
    storage = get_storage()
    storage._check_user_management_enabled()
    
    try:
        users, total = storage.list_users(limit=limit, offset=offset)
        return UsersListResponse(
            users=[UserResponse(**u.model_dump()) for u in users],
            total=total,
            limit=limit,
            offset=offset
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=UserResponse, status_code=201)
async def create_user(user_create: UserCreate):
    """Create a new user."""
    storage = get_storage()
    storage._check_user_management_enabled()
    
    try:
        user = storage.create_user(user_create)
        return UserResponse(**user.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: str):
    """Get a user by ID."""
    storage = get_storage()
    storage._check_user_management_enabled()
    
    try:
        user = storage.get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail=f"User not found: {user_id}")
        return UserResponse(**user.model_dump())
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{user_id}/data", response_model=CreateDataResponse)
async def create_data_for_user(
    user_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    file: Optional[UploadFile] = File(None),
    content: Optional[str] = Form(None),
    name: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    memory_ids: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    exclusive: Optional[str] = Form(None),
    purpose: Optional[str] = Form(None),
    forward_to_webhook: Optional[str] = Form(None),
    url: Optional[str] = Form(None),
    mime_type: Optional[str] = Form(None),
    is_downloaded: Optional[str] = Form(None),
    session_id: Optional[str] = Form(None),
    timeline_id: Optional[str] = Form(None),
    device_type: Optional[str] = Form(None),
    device_os: Optional[str] = Form(None),
    device_browser: Optional[str] = Form(None),
    device_app_version: Optional[str] = Form(None),
    device_user_agent: Optional[str] = Form(None),
    device_screen_width: Optional[int] = Form(None),
    device_screen_height: Optional[int] = Form(None),
    device_timezone: Optional[str] = Form(None),
    device_language: Optional[str] = Form(None),
    device_cpu_cores: Optional[int] = Form(None),
    device_memory_gb: Optional[float] = Form(None),
    device_connection_type: Optional[str] = Form(None),
    device_id: Optional[str] = Form(None),
    org_id: Optional[str] = Form(None),
    project_id: Optional[str] = Form(None),
    external_id: Optional[str] = Form(None),
):
    """Upload data as the given user (user ID in path).

    Same behavior as POST /api/v1/data with form field owner_user_id. The path
    user_id is always written to metadata and memory. Use this endpoint when the
    client sends user ID (e.g. UI uploads).
    """
    logger.info("create_data_for_user: path user_id=%r (multitenant path will use this)", user_id)
    return await _create_data_impl(
        request,
        background_tasks,
        owner_user_id=user_id,
        file=file,
        content=content,
        name=name,
        description=description,
        memory_ids=memory_ids,
        tags=tags,
        exclusive=exclusive,
        purpose=purpose,
        forward_to_webhook=forward_to_webhook,
        url=url,
        mime_type=mime_type,
        is_downloaded=is_downloaded,
        session_id=session_id,
        timeline_id=timeline_id,
        device_type=device_type,
        device_os=device_os,
        device_browser=device_browser,
        device_app_version=device_app_version,
        device_user_agent=device_user_agent,
        device_screen_width=device_screen_width,
        device_screen_height=device_screen_height,
        device_timezone=device_timezone,
        device_language=device_language,
        device_cpu_cores=device_cpu_cores,
        device_memory_gb=device_memory_gb,
        device_connection_type=device_connection_type,
        device_id=device_id,
        org_id=org_id,
        project_id=project_id,
        external_id=external_id,
    )


@router.get("/{user_id}/data", response_model=UserAllDataResponse)
async def get_user_all_data(user_id: str):
    """Return all data owned by *user_id* in a single call.

    Fetches the user profile, every memory, every prompt template, and every
    skill associated with the user.
    """
    storage = get_storage()
    storage._check_user_management_enabled()

    user = storage.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"User not found: {user_id}")

    try:
        memories, _ = storage.list_memories(user_id=user_id, limit=10_000)
        prompts = storage.list_prompts(user=user_id)
        skills = storage.list_skills(user=user_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch user data: {exc}")

    return UserAllDataResponse(
        user=UserResponse(**user.model_dump()),
        memories=memories,
        prompts=prompts,
        skills=skills,
        memory_count=len(memories),
        prompt_count=len(prompts),
        skill_count=len(skills),
    )


@router.get("/username/{username}", response_model=UserResponse)
async def get_user_by_username(username: str):
    """Get a user by username."""
    storage = get_storage()
    storage._check_user_management_enabled()
    
    try:
        user = storage.get_user_by_username(username)
        if not user:
            raise HTTPException(status_code=404, detail=f"User not found: {username}")
        return UserResponse(**user.model_dump())
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(user_id: str, user_update: UserUpdate):
    """Update a user."""
    storage = get_storage()
    storage._check_user_management_enabled()
    
    try:
        user = storage.update_user(user_id, user_update)
        if not user:
            raise HTTPException(status_code=404, detail=f"User not found: {user_id}")
        return UserResponse(**user.model_dump())
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{user_id}")
async def delete_user(user_id: str):
    """Delete a user and all associated data."""
    storage = get_storage()
    storage._check_user_management_enabled()
    
    try:
        success = storage.delete_user(user_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"User not found: {user_id}")
        return {"message": "User deleted", "user_id": user_id}
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# API Key Endpoints
# =============================================================================

@router.get("/{user_id}/api-keys", response_model=List[APIKeyResponse], tags=["API Keys"])
async def list_api_keys(user_id: str, request: Request):
    """List API keys for a user (without the actual key values)."""
    _require_self_or_platform(request, user_id)
    storage = get_storage()
    storage._check_user_management_enabled()
    
    try:
        # Verify user exists
        user = storage.get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail=f"User not found: {user_id}")
        
        keys = storage.list_api_keys(user_id)
        return keys
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{user_id}/api-keys", response_model=APIKeyResponse, status_code=201, tags=["API Keys"])
async def create_api_key(user_id: str, key_create: APIKeyCreate, request: Request):
    """
    Create an API key for a user.
    
    **Important**: The API key is only returned once. Store it securely!
    """
    _require_self_or_platform(request, user_id)
    storage = get_storage()
    storage._check_user_management_enabled()
    
    try:
        # Verify user exists
        user = storage.get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail=f"User not found: {user_id}")
        
        key_response = storage.create_api_key(user_id, key_create)
        if not key_response:
            raise HTTPException(status_code=500, detail="Failed to create API key")
        return key_response
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{user_id}/api-keys/{key_id}", tags=["API Keys"])
async def delete_api_key(
    user_id: str,
    key_id: str,
    request: Request,
    allow_empty: bool = Query(
        False,
        description="If true, allow revoking the last remaining key (host may lock itself out).",
    ),
):
    """Revoke an API key."""
    _require_self_or_platform(request, user_id)
    storage = get_storage()
    storage._check_user_management_enabled()
    
    try:
        # Verify user exists
        user = storage.get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail=f"User not found: {user_id}")

        existing = storage.list_api_keys(user_id)
        if len(existing) <= 1 and not allow_empty:
            raise HTTPException(
                status_code=400,
                detail="Cannot revoke the last API key; create a replacement first "
                "(or pass allow_empty=true)",
            )
        
        success = storage.delete_api_key(user_id, key_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"API key not found: {key_id}")
        return {"message": "API key deleted", "key_id": key_id}
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
