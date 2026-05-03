from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from app.storage import get_storage
from app.models import Skill, SkillCreate, SkillUpdate

router = APIRouter(prefix="/api/v1/ai/skills", tags=["AI Skills"])


@router.get("")
async def list_skills(
    data_id: Optional[str] = Query(default=None, description="Filter by data ID"),
    user_id: Optional[str] = Query(default=None, description="Filter by user ID"),
    tag: Optional[str] = Query(default=None, description="Filter by tag"),
):
    """
    List skills with optional filtering.

    - Filter by data_id to get skills for specific data
    - Filter by tag for skill categories
    - Filter by user_id for user-specific skills
    """
    try:
        storage = get_storage()
        storage._check_ai_enabled()
        skills = storage.list_skills(user=user_id, data_id=data_id, tag=tag)
        return {"skills": skills, "total": len(skills)}
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=Skill, status_code=201)
async def create_skill(skill_create: SkillCreate):
    """Create a new AI agent skill."""
    try:
        storage = get_storage()
        storage._check_ai_enabled()
        skill = storage.create_skill(skill_create)
        if not skill:
            raise HTTPException(status_code=500, detail="Failed to create skill")
        return skill
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{skill_id}", response_model=Skill)
async def get_skill(skill_id: str):
    """Get a specific skill by ID."""
    try:
        storage = get_storage()
        storage._check_ai_enabled()
        skill = storage.get_skill(skill_id)
        if not skill:
            raise HTTPException(status_code=404, detail=f"Skill not found: {skill_id}")
        return skill
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Skill not found: {skill_id}")
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{skill_id}", response_model=Skill)
async def update_skill(skill_id: str, skill_update: SkillUpdate):
    """Update an AI agent skill."""
    try:
        storage = get_storage()
        storage._check_ai_enabled()
        skill = storage.update_skill(skill_id, skill_update)
        if not skill:
            raise HTTPException(status_code=404, detail=f"Skill not found: {skill_id}")
        return skill
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Skill not found: {skill_id}")
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{skill_id}")
async def delete_skill(skill_id: str):
    """Delete an AI agent skill."""
    try:
        storage = get_storage()
        storage._check_ai_enabled()
        success = storage.delete_skill(skill_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Skill not found: {skill_id}")
        return {"message": "Skill deleted", "skill_id": skill_id}
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
