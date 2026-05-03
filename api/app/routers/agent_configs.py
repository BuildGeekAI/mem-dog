from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from app.storage import get_storage
from app.models import AgentConfig, AgentConfigCreate, AgentConfigUpdate

router = APIRouter(prefix="/api/v1/ai/agent-configs", tags=["AI Agent Configs"])


@router.get("")
async def list_agent_configs(
    user_id: Optional[str] = Query(default=None, description="Filter by user ID"),
    agent_type: Optional[str] = Query(default=None, description="Filter by agent type"),
):
    """List agent configs with optional filtering by user and/or agent type."""
    try:
        storage = get_storage()
        storage._check_ai_enabled()
        configs = storage.list_agent_configs(user_id=user_id, agent_type=agent_type)
        return {"configs": configs, "total": len(configs)}
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=AgentConfig, status_code=201)
async def create_agent_config(create: AgentConfigCreate):
    """Create a new agent pipeline config."""
    try:
        storage = get_storage()
        storage._check_ai_enabled()
        cfg = storage.create_agent_config(create)
        return cfg
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/resolve/{agent_type}")
async def resolve_agent_config(
    agent_type: str,
    user_id: Optional[str] = Query(default=None, description="User ID for override lookup"),
):
    """Resolve the effective agent config for a given agent type.

    Returns user override if exists, else system default, else 404.
    """
    try:
        storage = get_storage()
        storage._check_ai_enabled()
        cfg = storage.resolve_agent_config(agent_type, user_id=user_id)
        if not cfg:
            raise HTTPException(status_code=404, detail=f"No agent config for type: {agent_type}")
        return cfg
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{config_id}", response_model=AgentConfig)
async def get_agent_config(config_id: str):
    """Get a specific agent config by ID."""
    try:
        storage = get_storage()
        storage._check_ai_enabled()
        cfg = storage.get_agent_config(config_id)
        return cfg
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Agent config not found: {config_id}")
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{config_id}", response_model=AgentConfig)
async def update_agent_config(config_id: str, updates: AgentConfigUpdate):
    """Update an agent pipeline config."""
    try:
        storage = get_storage()
        storage._check_ai_enabled()
        cfg = storage.update_agent_config(config_id, updates)
        return cfg
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Agent config not found: {config_id}")
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{config_id}")
async def delete_agent_config(config_id: str):
    """Delete an agent pipeline config."""
    try:
        storage = get_storage()
        storage._check_ai_enabled()
        success = storage.delete_agent_config(config_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Agent config not found: {config_id}")
        return {"message": "Agent config deleted", "config_id": config_id}
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
