import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from app.storage import get_storage
from app.models import (
    AIEngineType, AIEngineConfig, AIEngineConfigCreate, AIEngineConfigUpdate,
    AIEngineConfigResponse,
    UserAIPreferences, UserAIPreferencesUpdate,
    GlobalAIAvailability, SystemAIConfigResponse, ProviderInfo,
)
from app import config
from app import model_catalog
from app import smart_routing
from app.crypto import encrypt_api_key, decrypt_api_key, is_encryption_available
from app.provider_registry import get_registry, get_provider
from app import provider_service

logger = logging.getLogger("mem_dog.ai_config")

router = APIRouter(prefix="/api/v1/ai", tags=["AI Configuration"])


@router.get("/system-config", response_model=SystemAIConfigResponse)
async def get_system_ai_config():
    """
    Get system AI configuration.
    
    Returns whether AI features are enabled and if system keys are available.
    """
    available = config.is_system_ai_available()
    return SystemAIConfigResponse(
        system_ai_available=available,
        system_engine_type="gemini",
        system_embedding_model=config.SYSTEM_GEMINI_MODEL_EMBEDDING,
        system_completion_model=config.SYSTEM_GEMINI_MODEL_COMPLETION,
        message=(
            "System Gemini key available — you can use AI features without your own API key."
            if available else
            "No system AI key configured. Configure your own engine to use AI features."
        ),
    )


# =============================================================================
# Self-hostable model catalog
# =============================================================================

@router.get("/model-catalog")
async def get_model_catalog(
    family: Optional[str] = Query(None, description="Filter by model family (mistral, llama, gemma, phi, qwen, deepseek)"),
    role: Optional[str] = Query(None, description="Filter by recommended_role (leaf, mid-tier, orchestrator)"),
    max_memory_gb: Optional[float] = Query(None, description="Filter to models fitting within this many GB of RAM"),
):
    """
    Return the catalog of self-hostable open-source models.

    Optionally filter by ``family``, ``role``, or ``max_memory_gb``.
    """
    models = dict(model_catalog.SELF_HOSTABLE_MODELS)

    if family:
        models = {k: v for k, v in models.items() if v["family"] == family.lower()}
    if role:
        models = {k: v for k, v in models.items() if v["recommended_role"] == role.lower()}
    if max_memory_gb is not None:
        models = {k: v for k, v in models.items() if v["memory_required_gb"] <= max_memory_gb}

    return {
        "total": len(models),
        "families": model_catalog.FAMILIES,
        "roles": model_catalog.ROLES,
        "models": models,
    }


@router.get("/model-catalog/{model_id}")
async def get_model_catalog_entry(model_id: str):
    """Return a single model entry from the catalog by its key (e.g. ``gemma-3-4b``)."""
    entry = model_catalog.SELF_HOSTABLE_MODELS.get(model_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found in catalog")
    return entry


# =============================================================================
# Deployment options (GCP VM and Cloud Run)
# =============================================================================

def _load_deployment_options_json(filename: str) -> dict:
    """Load a JSON file from app/data. Used for VM and Cloud Run options."""
    data_dir = Path(__file__).resolve().parent.parent / "data"
    path = data_dir / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"Deployment options file not found: {filename}")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        raise HTTPException(status_code=500, detail=f"Failed to load deployment options: {e}")


@router.get("/deployment-options/vm")
async def get_vm_deployment_options():
    """
    Return GCP Compute Engine VM instance types and per-instance model options.

    Aligns with scripts/gcp-vm-options.json. Each instance has gcp_machine_type,
    gcp_accelerator_*, and a list of models with catalog_model_id and ollama_tag.
    """
    return _load_deployment_options_json("gcp-vm-options.json")


@router.get("/deployment-options/cloudrun")
async def get_cloudrun_deployment_options():
    """
    Return GCP Cloud Run instance types and tier-to-model mapping.

    Aligns with scripts/gcp-cloudrun-options.json. Includes CPU/GPU and
    tier (small/medium/large/very-large) options with catalog_model_id.
    """
    return _load_deployment_options_json("gcp-cloudrun-options.json")


# =============================================================================
# Agent Processing Defaults
# =============================================================================

# Agent types where AI processing is OFF by default
# (Previously included json, chat, channel_message, binary_blob — now enabled
#  since small-tier types route to self-hosted Phi-3 Mini at zero API cost.)
_PROCESSING_DISABLED_BY_DEFAULT: set[str] = set()

# All known agent types
_ALL_AGENT_TYPES = [
    # Media
    "video_url", "video_stream", "audio_url", "audio_stream", "image", "image_batch",
    # Documents
    "pdf", "office_doc", "markdown", "html_doc",
    # Structured
    "json", "xml", "csv", "yaml",
    # Code / Logs
    "code", "log_stream", "log_file",
    # Communication
    "email", "chat", "channel_message", "web_page", "feed", "calendar",
    # Sensor
    "sensor", "iot_sensor", "gps", "biometric",
    # Spatial
    "model_3d", "lidar", "geospatial",
    # Binary
    "binary_blob", "archive", "time_series", "medical_imaging",
    # Specialized
    "vehicle_telemetry", "infrastructure", "satellite", "conferencing",
    "scientific", "industrial", "financial",
    # Download
    "url_download",
]

AGENT_PROCESSING_DEFAULTS: dict[str, bool] = {
    t: (t not in _PROCESSING_DISABLED_BY_DEFAULT) for t in _ALL_AGENT_TYPES
}


@router.get("/pipeline-models")
async def get_pipeline_models():
    """Return current data pipeline model configuration (tier models + fallback).

    Shows which Ollama Cloud model is used for each tier and what Gemini
    model is configured as fallback.
    """
    prefer_gemini = config._resolve(
        "AGENT_PREFER_GEMINI", "ai.agent_prefer_gemini", "false"
    ).lower() in ("1", "true", "yes")

    has_ollama_cloud = bool(config.OLLAMA_CLOUD_API_KEY)
    return {
        "primary_provider": "gemini" if prefer_gemini else "ollama_cloud",
        "fallback_provider": "ollama_cloud" if prefer_gemini else "gemini",
        "tier_models": {
            "small": config.OLLAMA_CLOUD_MODEL_SMALL,
            "medium": config.OLLAMA_CLOUD_MODEL_MEDIUM,
            "large": config.OLLAMA_CLOUD_MODEL_LARGE,
            "multimodal": config.OLLAMA_CLOUD_MODEL_MULTIMODAL,
        },
        "fallback_model": config.DATA_PIPELINE_AI_FALLBACK_MODEL,
        "primary_model": config.DATA_PIPELINE_AI_PRIMARY_MODEL,
        "embedding": {
            "primary": config.OLLAMA_CLOUD_MODEL_EMBEDDING if has_ollama_cloud else config.SYSTEM_GEMINI_MODEL_EMBEDDING,
            "primary_provider": "ollama_cloud" if has_ollama_cloud else "gemini",
            "fallback": config.SYSTEM_GEMINI_MODEL_EMBEDDING if has_ollama_cloud else None,
            "fallback_provider": "gemini" if has_ollama_cloud else None,
        },
    }


@router.get("/agent-processing-defaults")
async def get_agent_processing_defaults():
    """
    Return the default AI-processing on/off flag for every known agent type.

    OFF by default: channel_message, chat, json, binary_blob.
    ON by default: everything else.
    """
    return AGENT_PROCESSING_DEFAULTS


@router.get("/engines", response_model=GlobalAIAvailability)
async def get_available_engines():
    """
    Get all available AI engine configurations.
    
    Returns system-provided engines and user-configured engines.
    """
    try:
        storage = get_storage()
        storage._check_ai_enabled()
        availability = storage.get_global_ai_availability()
        return availability
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# User AI Engine Configuration
# =============================================================================


def _to_response(cfg: AIEngineConfig) -> AIEngineConfigResponse:
    """Convert an internal AIEngineConfig to a safe response (no encrypted key)."""
    return AIEngineConfigResponse(
        engine_id=cfg.engine_id,
        user=cfg.user,
        engine_type=cfg.engine_type,
        name=cfg.name,
        base_url=cfg.base_url,
        is_enabled=cfg.is_enabled,
        has_api_key=bool(cfg.api_key_encrypted),
        available_models=cfg.available_models,
        discovered_models=cfg.discovered_models,
        last_tested_at=cfg.last_tested_at,
        last_test_status=cfg.last_test_status,
        created_at=cfg.created_at,
        updated_at=cfg.updated_at,
    )


@router.get("/users/{user_id}/engines")
async def list_user_engines(user_id: str):
    """List AI engine configurations for a user."""
    try:
        storage = get_storage()
        storage._check_ai_enabled()
        configs = storage.list_engine_configs(user_id)
        return {"user_id": user_id, "engines": [_to_response(c) for c in configs]}
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/users/{user_id}/engines", status_code=201, response_model=AIEngineConfigResponse)
async def create_user_engine(user_id: str, engine_config: AIEngineConfigCreate):
    """Create an AI engine configuration for a user."""
    try:
        storage = get_storage()
        storage._check_ai_enabled()
        now = datetime.now(timezone.utc).isoformat()

        encrypted_key = None
        if engine_config.api_key:
            if is_encryption_available():
                encrypted_key = encrypt_api_key(engine_config.api_key)
            else:
                encrypted_key = engine_config.api_key
                logger.warning("Encryption not available; storing API key in plain text")

        ai_config = AIEngineConfig(
            engine_id=str(uuid.uuid4()),
            user=user_id,
            engine_type=engine_config.engine_type,
            name=engine_config.name,
            base_url=engine_config.base_url,
            is_enabled=engine_config.is_enabled,
            api_key_encrypted=encrypted_key,
            created_at=now,
            updated_at=now,
        )
        storage.store_engine_config(ai_config)
        return _to_response(ai_config)
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/users/{user_id}/engines/{config_id}", response_model=AIEngineConfigResponse)
async def get_user_engine(user_id: str, config_id: str):
    """Get a specific AI engine configuration."""
    try:
        storage = get_storage()
        storage._check_ai_enabled()
        ai_config = storage.get_engine_config(user_id, config_id)
        return _to_response(ai_config)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Engine config not found: {config_id}")
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/users/{user_id}/engines/{config_id}", response_model=AIEngineConfigResponse)
async def update_user_engine(user_id: str, config_id: str, engine_update: AIEngineConfigUpdate):
    """Update an AI engine configuration."""
    try:
        storage = get_storage()
        storage._check_ai_enabled()
        existing = storage.get_engine_config(user_id, config_id)
        update_data = engine_update.model_dump(exclude_unset=True)
        if "api_key" in update_data:
            raw_key = update_data.pop("api_key")
            if raw_key:
                if is_encryption_available():
                    update_data["api_key_encrypted"] = encrypt_api_key(raw_key)
                else:
                    update_data["api_key_encrypted"] = raw_key
                    logger.warning("Encryption not available; storing API key in plain text")
            else:
                update_data["api_key_encrypted"] = None
        updated = existing.model_copy(update={
            **update_data,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        storage.store_engine_config(updated)
        return _to_response(updated)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Engine config not found: {config_id}")
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/users/{user_id}/engines/{config_id}")
async def delete_user_engine(user_id: str, config_id: str):
    """Delete an AI engine configuration."""
    try:
        storage = get_storage()
        storage._check_ai_enabled()
        storage.delete_engine_config(user_id, config_id)
        return {"message": "Engine config deleted", "config_id": config_id}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Engine config not found: {config_id}")
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# User AI Preferences
# =============================================================================

@router.get("/users/{user_id}/preferences", response_model=UserAIPreferences)
async def get_user_preferences(user_id: str):
    """Get AI preferences for a user."""
    try:
        storage = get_storage()
        storage._check_ai_enabled()
        prefs = storage.get_user_preferences(user_id)
        if prefs is None:
            from datetime import datetime
            now = datetime.utcnow().isoformat() + "Z"
            prefs = UserAIPreferences(user=user_id, created_at=now, updated_at=now)
        return prefs
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/users/{user_id}/preferences", response_model=UserAIPreferences)
async def update_user_preferences(user_id: str, prefs_update: UserAIPreferencesUpdate):
    """Update AI preferences for a user."""
    try:
        storage = get_storage()
        storage._check_ai_enabled()
        existing = storage.get_user_preferences(user_id)
        if existing is None:
            from datetime import datetime
            now = datetime.utcnow().isoformat() + "Z"
            existing = UserAIPreferences(user=user_id, created_at=now, updated_at=now)
        update_data = prefs_update.model_dump(exclude_unset=True)
        merged = existing.model_copy(update=update_data)
        storage.store_user_preferences(merged)
        prefs = merged
        return prefs
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Provider Registry & Model Garden endpoints
# =============================================================================


@router.get("/provider-registry")
async def get_provider_registry():
    """Return the static provider catalog for the Model Garden UI."""
    registry = get_registry()
    return {
        "providers": [info.model_dump() for info in registry.values()],
    }


@router.post("/users/{user_id}/engines/{config_id}/test")
async def test_engine(user_id: str, config_id: str):
    """Test connectivity for a user's engine configuration."""
    try:
        storage = get_storage()
        storage._check_ai_enabled()
        ai_config = storage.get_engine_config(user_id, config_id)

        # Decrypt API key for testing
        api_key = None
        if ai_config.api_key_encrypted:
            try:
                api_key = decrypt_api_key(ai_config.api_key_encrypted)
            except Exception:
                api_key = ai_config.api_key_encrypted  # May be plain text (legacy)

        result = await provider_service.test_provider(
            engine_type=ai_config.engine_type.value,
            api_key=api_key,
            base_url=ai_config.base_url,
        )

        now = datetime.now(timezone.utc).isoformat()
        updated = ai_config.model_copy(update={
            "last_tested_at": now,
            "last_test_status": "success" if result["ok"] else "error",
            "last_test_error": result.get("error"),
            "updated_at": now,
        })
        storage.store_engine_config(updated)

        return {
            "ok": result["ok"],
            "latency_ms": result.get("latency_ms"),
            "error": result.get("error"),
            "tested_at": now,
        }
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Engine config not found: {config_id}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/users/{user_id}/engines/{config_id}/discover-models")
async def discover_engine_models(user_id: str, config_id: str):
    """Discover available models for a user's engine configuration."""
    try:
        storage = get_storage()
        storage._check_ai_enabled()
        ai_config = storage.get_engine_config(user_id, config_id)

        api_key = None
        if ai_config.api_key_encrypted:
            try:
                api_key = decrypt_api_key(ai_config.api_key_encrypted)
            except Exception:
                api_key = ai_config.api_key_encrypted

        models = await provider_service.discover_models(
            engine_type=ai_config.engine_type.value,
            api_key=api_key,
            base_url=ai_config.base_url,
        )

        now = datetime.now(timezone.utc).isoformat()
        updated = ai_config.model_copy(update={
            "discovered_models": models,
            "updated_at": now,
        })
        storage.store_engine_config(updated)

        return {"models": models, "count": len(models)}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Engine config not found: {config_id}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/users/{user_id}/available-models")
async def get_user_available_models(user_id: str):
    """Aggregate available models from all user-configured providers + system providers."""
    try:
        storage = get_storage()
        storage._check_ai_enabled()
        configs = storage.list_engine_configs(user_id)
        registry = get_registry()

        providers = []
        for cfg in configs:
            if not cfg.is_enabled:
                continue
            provider_info = registry.get(cfg.engine_type.value if hasattr(cfg.engine_type, 'value') else cfg.engine_type)
            litellm_prefix = provider_info.litellm_prefix if provider_info else ""
            models = cfg.discovered_models or (provider_info.default_models if provider_info else [])
            providers.append({
                "engine_id": cfg.engine_id,
                "name": cfg.name,
                "engine_type": cfg.engine_type.value if hasattr(cfg.engine_type, 'value') else cfg.engine_type,
                "litellm_prefix": litellm_prefix,
                "models": models,
                "source": "user",
            })

        # Add system provider if available
        if config.is_system_ai_available():
            providers.append({
                "engine_id": "system-gemini",
                "name": "System Gemini",
                "engine_type": "gemini",
                "litellm_prefix": "gemini/",
                "models": ["gemini-2.5-flash-preview-05-20", "gemini-2.5-pro-preview-05-06", "gemini-3.1-pro-preview"],
                "source": "system",
            })

        return {"providers": providers}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/users/{user_id}/engines/{config_id}/credentials")
async def get_engine_credentials(user_id: str, config_id: str):
    """Internal-only: return decrypted credentials for webhook processor."""
    try:
        storage = get_storage()
        storage._check_ai_enabled()
        ai_config = storage.get_engine_config(user_id, config_id)

        api_key = None
        if ai_config.api_key_encrypted:
            try:
                api_key = decrypt_api_key(ai_config.api_key_encrypted)
            except Exception:
                api_key = ai_config.api_key_encrypted

        return {
            "engine_type": ai_config.engine_type.value if hasattr(ai_config.engine_type, 'value') else ai_config.engine_type,
            "api_key": api_key,
            "base_url": ai_config.base_url,
        }
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Engine config not found: {config_id}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Smart Routing endpoints
# ---------------------------------------------------------------------------


@router.get("/ollama-cloud-models")
async def get_ollama_cloud_models(refresh: bool = False):
    """Return enriched model cards from Ollama Cloud (cached 1hr)."""
    try:
        models = smart_routing.fetch_ollama_cloud_models(refresh=refresh)
        return {
            "models": models,
            "count": len(models),
            "categories": smart_routing.DATA_TYPE_CATEGORIES,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/smart-routing-suggestions")
async def get_smart_routing_suggestions():
    """Return system-suggested routing table for all data types."""
    try:
        models = smart_routing.fetch_ollama_cloud_models()
        table = smart_routing.get_routing_table(models)
        return {
            "suggestions": table,
            "data_type_requirements": smart_routing.DATA_TYPE_REQUIREMENTS,
            "categories": smart_routing.DATA_TYPE_CATEGORIES,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/smart-routing-config/{user_id}")
async def get_smart_routing_config(user_id: str):
    """Return merged routing: system suggestions + user overrides."""
    try:
        storage = get_storage()
        storage._check_ai_enabled()
        prefs = storage.get_user_preferences(user_id)
        overrides = getattr(prefs, "smart_routing_overrides", {}) or {}
        models = smart_routing.fetch_ollama_cloud_models()
        merged = smart_routing.get_merged_routing(overrides, models)
        return {
            "routing": merged,
            "categories": smart_routing.DATA_TYPE_CATEGORIES,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
