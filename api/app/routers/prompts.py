from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List

from app import config
from app.storage import get_storage
from app.models import Prompt, PromptCreate, PromptUpdate

router = APIRouter(prefix="/api/v1/ai/prompts", tags=["AI Prompts"])


@router.get("")
async def list_prompts(
    data_id: Optional[str] = Query(default=None, description="Filter by data ID"),
    category: Optional[str] = Query(default=None, description="Filter by category"),
    user_id: Optional[str] = Query(default=None, description="Filter by user ID")
):
    """
    List prompts with optional filtering.
    
    - Filter by data_id to get prompts for specific data
    - Filter by category for prompt types
    - Filter by user_id for user-specific prompts
    """
    try:
        storage = get_storage()
        storage._check_ai_enabled()
        user = user_id or config.DEFAULT_USER_ID
        prompts = storage.list_prompts(user=user, data_id=data_id)
        if category:
            prompts = [p for p in prompts if getattr(p, 'category', None) == category]
        return {"prompts": prompts, "total": len(prompts)}
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=Prompt, status_code=201)
async def create_prompt(prompt_create: PromptCreate):
    """Create a new prompt template."""
    try:
        storage = get_storage()
        storage._check_ai_enabled()
        prompt = storage.create_prompt(prompt_create)
        if not prompt:
            raise HTTPException(status_code=500, detail="Failed to create prompt")
        return prompt
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{prompt_id}", response_model=Prompt)
async def get_prompt(prompt_id: str):
    """Get a specific prompt by ID."""
    try:
        storage = get_storage()
        storage._check_ai_enabled()
        prompt = storage.get_prompt(prompt_id)
        if not prompt:
            raise HTTPException(status_code=404, detail=f"Prompt not found: {prompt_id}")
        return prompt
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{prompt_id}", response_model=Prompt)
async def update_prompt(prompt_id: str, prompt_update: PromptUpdate):
    """Update a prompt template."""
    try:
        storage = get_storage()
        storage._check_ai_enabled()
        prompt = storage.update_prompt(prompt_id, prompt_update)
        if not prompt:
            raise HTTPException(status_code=404, detail=f"Prompt not found: {prompt_id}")
        return prompt
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{prompt_id}")
async def delete_prompt(prompt_id: str):
    """Delete a prompt template."""
    try:
        storage = get_storage()
        storage._check_ai_enabled()
        success = storage.delete_prompt(prompt_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Prompt not found: {prompt_id}")
        return {"message": "Prompt deleted", "prompt_id": prompt_id}
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
