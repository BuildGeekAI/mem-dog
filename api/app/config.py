import json
import logging
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load shared AI model defaults from config/ai.env (repo root), then api/.env.
# ai.env populates GEMINI_MODEL, GEMINI_MODEL_EMBEDDING, etc. so _resolve()
# picks them up automatically via os.getenv().  api/.env can still override.
_repo_root = Path(__file__).resolve().parent.parent.parent
load_dotenv(_repo_root / "config" / "ai.env")

_api_dir = Path(__file__).resolve().parent.parent
load_dotenv(_api_dir / ".env")

_config_logger = logging.getLogger("mem_dog.config")

# =============================================================================
# Storage Backend Selection
# =============================================================================
# Auto-detect: if GCP env vars are present, use GCS; otherwise default to local.
# Can be overridden explicitly with STORAGE_BACKEND=local, STORAGE_BACKEND=gcs,
# or STORAGE_BACKEND=supabase.
#
# STORAGE_BACKEND=supabase — hybrid backend:
#   - Raw binary data stays in GCS (RAW_BUCKET required)
#   - All other structured data (meta, memories, viewpoints, users, prompts,
#     skills, stats, channels, index, ai_config) → Supabase PostgreSQL
#     (mem_dog_blobs table; requires SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY)
#   - Vector embeddings → mem_dog_embeddings pgvector table (same credentials)
#   Apply api/supabase/mem_dog_blobs.sql and api/supabase/mem_dog_embeddings.sql in Supabase (SQL Editor or migrations).

SYSTEM_CONFIG_BUCKET = os.getenv("SYSTEM_CONFIG_BUCKET", "")
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

_explicit_backend = os.getenv("STORAGE_BACKEND", "").lower()
if _explicit_backend:
    STORAGE_BACKEND = _explicit_backend
elif GCP_PROJECT_ID or SYSTEM_CONFIG_BUCKET:
    STORAGE_BACKEND = "gcs"
else:
    STORAGE_BACKEND = "local"

# Local storage directory (only used when STORAGE_BACKEND=local).
MEM_DOG_DATA_DIR = os.getenv("MEM_DOG_DATA_DIR", str(Path.home() / ".mem-dog"))

_config_logger.info(
    "Storage backend: %s%s",
    STORAGE_BACKEND,
    f" (data dir: {MEM_DOG_DATA_DIR})" if STORAGE_BACKEND == "local" else "",
)

# =============================================================================
# System Configuration Bucket (GCS only)
# =============================================================================

# The loaded system config dict (populated by _load_system_config).
_system_config: dict = {}


def _load_system_config() -> dict:
    """Load platform-config.json from the system config GCS bucket.

    Returns the parsed dict on success, or an empty dict if the bucket is not
    configured, the storage backend is local, or the file cannot be read.
    Errors are logged as warnings so the application can still fall back to
    environment variables.
    """
    if STORAGE_BACKEND == "local":
        return {}

    if not SYSTEM_CONFIG_BUCKET:
        return {}

    try:
        from google.cloud import storage as gcs_storage
        from google.cloud.exceptions import NotFound

        project = GCP_PROJECT_ID if GCP_PROJECT_ID else None
        client = gcs_storage.Client(project=project)
        bucket = client.bucket(SYSTEM_CONFIG_BUCKET)
        blob = bucket.blob("platform-config.json")
        content = blob.download_as_string()
        data = json.loads(content)
        _config_logger.info(
            "Loaded system config from gs://%s/platform-config.json (version %s)",
            SYSTEM_CONFIG_BUCKET,
            data.get("version", "unknown"),
        )
        return data
    except ImportError:
        _config_logger.warning(
            "google-cloud-storage not installed; skipping system config bucket"
        )
        return {}
    except NotFound:
        _config_logger.warning(
            "platform-config.json not found in gs://%s; using env vars only",
            SYSTEM_CONFIG_BUCKET,
        )
        return {}
    except Exception as exc:
        _config_logger.warning(
            "Failed to load system config from gs://%s: %s; using env vars only",
            SYSTEM_CONFIG_BUCKET,
            exc,
        )
        return {}


def _resolve(env_var: str, sys_key: str, default: str = "") -> str:
    """Resolve a config value: env var wins, then system config, then default."""
    env_value = os.getenv(env_var)
    if env_value is not None and env_value != "":
        return env_value
    sys_value = _sys_get(sys_key)
    if sys_value is not None and sys_value != "":
        return str(sys_value)
    return default


def _sys_get(dotted_key: str):
    """Read a dotted key like 'buckets.raw' from the loaded system config."""
    obj = _system_config
    for part in dotted_key.split("."):
        if not isinstance(obj, dict):
            return None
        obj = obj.get(part)
        if obj is None:
            return None
    return obj


# Load system config at module init (before any config values are resolved).
# Skipped entirely when running with local storage backend.
_system_config = _load_system_config()

# =============================================================================
# API Key Authentication
# =============================================================================
# When set, every request (except /health, /docs, /redoc, /openapi.json)
# must include a matching X-API-Key header.  Leave blank to disable.
API_KEY = os.getenv("API_KEY", "")

# Supabase JWT secret — used to verify Bearer tokens from browser users.
# Same value as the JWT_SECRET in the supabase-secrets k8s Secret.
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")

# =============================================================================
# Host SaaS quotas (Phase F2) — 0 disables each check
# =============================================================================
QUOTA_INGEST_RPM = int(os.getenv("QUOTA_INGEST_RPM", "0") or "0")
QUOTA_MAX_BODY_BYTES = int(os.getenv("QUOTA_MAX_BODY_BYTES", "0") or "0")
QUOTA_MAX_STORAGE_BYTES_PER_PROJECT = int(
    os.getenv("QUOTA_MAX_STORAGE_BYTES_PER_PROJECT", "0") or "0"
)

# =============================================================================
# GCP / Bucket Configuration (used only when STORAGE_BACKEND=gcs)
# =============================================================================
# Resolution order: env var -> system config bucket -> default
# In local mode these values are irrelevant and ignored by the Storage layer.

RAW_BUCKET = _resolve("RAW_BUCKET", "buckets.raw")
META_BUCKET = _resolve("META_BUCKET", "buckets.meta")
USER_BUCKET = _resolve("USER_BUCKET", "buckets.users")
MEMORIES_BUCKET = _resolve("MEMORIES_BUCKET", "buckets.memories")

# =============================================================================
# OpenTelemetry Configuration
# =============================================================================

OTEL_ENABLED = _resolve("OTEL_ENABLED", "telemetry.otel_enabled", "true").lower() == "true"
OTEL_SERVICE_NAME = _resolve("OTEL_SERVICE_NAME", "telemetry.otel_service_name", "mem-dog-api")
OTEL_EXPORTER_OTLP_ENDPOINT = _resolve("OTEL_EXPORTER_OTLP_ENDPOINT", "telemetry.otel_exporter_otlp_endpoint")
OTEL_EXPORTER_OTLP_PROTOCOL = _resolve("OTEL_EXPORTER_OTLP_PROTOCOL", "telemetry.otel_exporter_otlp_protocol", "grpc")
LOG_LEVEL = _resolve("LOG_LEVEL", "app.log_level", "INFO").upper()

# =============================================================================
# AI Layer Bucket Configuration (used only when STORAGE_BACKEND=gcs)
# =============================================================================

PROMPTS_BUCKET = _resolve("PROMPTS_BUCKET", "buckets.prompts")
EMBEDDINGS_BUCKET = _resolve("EMBEDDINGS_BUCKET", "buckets.embeddings")
VIEWPOINTS_BUCKET = _resolve("VIEWPOINTS_BUCKET", "buckets.viewpoints")
AI_CONFIG_BUCKET = _resolve("AI_CONFIG_BUCKET", "buckets.ai_config")
SKILLS_BUCKET = _resolve("SKILLS_BUCKET", "buckets.skills")

# =============================================================================
# Statistics Bucket Configuration (used only when STORAGE_BACKEND=gcs)
# =============================================================================

STATS_BUCKET = _resolve("STATS_BUCKET", "buckets.stats")

# =============================================================================
# Channels Bucket — per-channel metadata (path <channel_type>/meta)
# =============================================================================
# Optional. When unset, channel metadata is stored in META_BUCKET under _channels/ prefix.
CHANNELS_BUCKET = _resolve("CHANNELS_BUCKET", "buckets.channels", "")

# Reverse-index bucket (can share META_BUCKET; set INDEX_BUCKET to use a dedicated one).
# When empty, index entries are written inside META_BUCKET under the `_idx/` prefix.
INDEX_BUCKET = _resolve("INDEX_BUCKET", "buckets.index")

# AI Encryption Key (for encrypting API keys at rest)
AI_ENCRYPTION_KEY = _resolve("AI_ENCRYPTION_KEY", "ai.ai_encryption_key")

# =============================================================================
# System Default AI Configuration
# =============================================================================
# This Gemini key is provided by the system as a fallback for users who don't
# configure their own keys.  Users can choose "custom" or "system" mode.

SYSTEM_GEMINI_API_KEY = _resolve("SYSTEM_GEMINI_API_KEY", "ai.system_gemini_api_key")
SYSTEM_GEMINI_MODEL_EMBEDDING = _resolve("SYSTEM_GEMINI_MODEL_EMBEDDING", "ai.system_gemini_model_embedding", os.getenv("GEMINI_MODEL_EMBEDDING", "gemini-embedding-001"))
SYSTEM_GEMINI_MODEL_COMPLETION = _resolve("SYSTEM_GEMINI_MODEL_COMPLETION", "ai.system_gemini_model_completion", os.getenv("GEMINI_MODEL", "gemini-3.1-pro-preview"))

# =============================================================================
# Data processing pipeline AI
# =============================================================================
# Used by the webhook agent and any API-side data processing. All inference
# uses Gemini 3.0 Flash by default; fallback is Ollama Cloud when primary fails.

DATA_PIPELINE_AI_PRIMARY_MODEL: str = _resolve(
    "DATA_PIPELINE_AI_PRIMARY_MODEL",
    "ai.data_pipeline_primary_model",
    os.getenv("GEMINI_LITELLM_MODEL", "gemini/gemini-3.1-pro-preview"),
)
DATA_PIPELINE_AI_FALLBACK_MODEL: str = _resolve(
    "DATA_PIPELINE_AI_FALLBACK_MODEL",
    "ai.data_pipeline_fallback_model",
    os.getenv("FALLBACK_LITELLM_MODEL", "gemini/gemini-3.1-pro-preview"),
)
DATA_PIPELINE_AI_FALLBACK_ENABLED: bool = (
    _resolve("DATA_PIPELINE_AI_FALLBACK_ENABLED", "ai.data_pipeline_fallback_enabled", "true").lower()
    in ("1", "true", "yes")
)
# API key for Ollama Cloud (LiteLLM OLLAMA_API_KEY). Optional; Ollama Cloud is skipped if unset.
OLLAMA_CLOUD_API_KEY: str = _resolve("OLLAMA_CLOUD_API_KEY", "ai.ollama_cloud_api_key", "")

# Per-tier Ollama Cloud models (primary provider for data pipeline).
OLLAMA_CLOUD_MODEL_SMALL: str = _resolve("OLLAMA_CLOUD_MODEL_SMALL", "ai.ollama_cloud_model_small", "ollama/gemma3:4b")
OLLAMA_CLOUD_MODEL_MEDIUM: str = _resolve("OLLAMA_CLOUD_MODEL_MEDIUM", "ai.ollama_cloud_model_medium", "ollama/gemma3:12b")
OLLAMA_CLOUD_MODEL_LARGE: str = _resolve("OLLAMA_CLOUD_MODEL_LARGE", "ai.ollama_cloud_model_large", "ollama/gemma3:27b")
OLLAMA_CLOUD_MODEL_MULTIMODAL: str = _resolve("OLLAMA_CLOUD_MODEL_MULTIMODAL", "ai.ollama_cloud_model_multimodal", "ollama/qwen3-vl:235b-cloud")
OLLAMA_CLOUD_MODEL_OMNI: str = _resolve("OLLAMA_CLOUD_MODEL_OMNI", "ai.ollama_cloud_model_omni", "ollama/qwen3.5:cloud")

# Ollama Cloud embedding model (used when OLLAMA_CLOUD_API_KEY is set).
OLLAMA_CLOUD_MODEL_EMBEDDING: str = _resolve("OLLAMA_CLOUD_MODEL_EMBEDDING", "ai.ollama_cloud_model_embedding", "embeddinggemma")
OLLAMA_CLOUD_API_BASE: str = _resolve("OLLAMA_CLOUD_API_BASE", "ai.ollama_cloud_api_base", "https://api.ollama.com")

# Local Ollama embedding server (in-cluster, no API key needed).
OLLAMA_LOCAL_API_BASE: str = _resolve(
    "OLLAMA_LOCAL_API_BASE", "ai.ollama_local_api_base",
    "http://ollama.webhook-pipeline.svc.cluster.local:11434"
)
OLLAMA_LOCAL_MODEL_EMBEDDING: str = _resolve(
    "OLLAMA_LOCAL_MODEL_EMBEDDING", "ai.ollama_local_model_embedding",
    "embeddinggemma"
)

# =============================================================================
# PostgreSQL (deprecated)
# =============================================================================
# Postgres is no longer used; all data is stored in GCS or local blob storage.
# POSTGRES_URL and is_postgres_enabled() are kept for backward compatibility only.

POSTGRES_URL: str = _resolve("POSTGRES_URL", "database.postgres_url", "")


def is_postgres_enabled() -> bool:
    """Deprecated. Always returns False; storage uses GCS/local only."""
    return False


def is_postgres_store_enabled() -> bool:
    """True when POSTGRES_URL is set; enables Postgres-backed store for testing CRUD API."""
    return bool(POSTGRES_URL and POSTGRES_URL.strip())


# =============================================================================
# Redis store (optional store layer: Redis Cloud or local Redis)
# =============================================================================
# REDIS_URL is resolved from env or system config (e.g. redis://localhost:6379/0
# for local, or Redis Cloud connection string). Use case determined by the layer above.

REDIS_URL: str = _resolve("REDIS_URL", "store.redis_url", "")


def is_redis_store_enabled() -> bool:
    """True when REDIS_URL is set; enables Redis-backed store layer."""
    return bool(REDIS_URL and REDIS_URL.strip())


# =============================================================================
# Supabase store (optional store layer)
# =============================================================================
# SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_KEY) for the store table.
# For server-side API: use the Cloud Run proxy URL (not the gateway) so the Supabase client
# can send Authorization/apikey. The gateway rejects Bearer tokens (validates as Google OAuth).
# When SUPABASE_URL points to the gateway (external clients), set SUPABASE_API_GATEWAY_KEY
# and use x-supabase-auth instead of Authorization (see k8s/api-gateway/openapi-spec.yaml).

SUPABASE_URL: str = _resolve("SUPABASE_URL", "store.supabase_url", "")
SUPABASE_KEY: str = _resolve("SUPABASE_SERVICE_ROLE_KEY", "store.supabase_service_role_key", "") or _resolve("SUPABASE_KEY", "store.supabase_key", "")
SUPABASE_API_GATEWAY_KEY: str = _resolve("SUPABASE_API_GATEWAY_KEY", "store.supabase_api_gateway_key", "")


# =============================================================================
# Webhook API Gateway (optional; for outbound webhook calls or system config)
# =============================================================================
# Set when deploy-api runs after deploy-webhook, or via MEM_DOG_WEBHOOK_GATEWAY_URL
# and MEM_DOG_WEBHOOK_API_KEY. Used when the API needs to know the webhook
# gateway URL and key (e.g. for display, config, or outbound webhook calls).

WEBHOOK_GATEWAY_URL: str = _resolve("WEBHOOK_GATEWAY_URL", "webhook.gateway_url", "")
WEBHOOK_API_KEY: str = _resolve("WEBHOOK_API_KEY", "webhook.api_key", "")


# =============================================================================
# Nango (integration platform — replaces custom OAuth/credential management)
# =============================================================================
NANGO_API_URL: str = _resolve("NANGO_API_URL", "nango.api_url", "")
NANGO_SECRET_KEY: str = _resolve("NANGO_SECRET_KEY", "nango.secret_key", "")


def is_supabase_store_enabled() -> bool:
    """True when SUPABASE_URL and SUPABASE_KEY are set; enables Supabase-backed store."""
    return bool(SUPABASE_URL and SUPABASE_URL.strip() and SUPABASE_KEY and SUPABASE_KEY.strip())


def is_supabase_storage_enabled() -> bool:
    """True when all credentials for STORAGE_BACKEND=supabase are present.

    Requires SUPABASE_URL, SUPABASE_KEY (or SUPABASE_SERVICE_ROLE_KEY), and
    RAW_BUCKET (for the GCS raw data store).
    """
    return bool(
        SUPABASE_URL and SUPABASE_URL.strip()
        and SUPABASE_KEY and SUPABASE_KEY.strip()
        and RAW_BUCKET and RAW_BUCKET.strip()
    )


# =============================================================================
# GCS store (optional store layer: direct GCS objects, no SQLite)
# =============================================================================
# STORE_GCS_BUCKET: GCS bucket for key-value store. Persists reliably to GCS objects.

STORE_GCS_BUCKET: str = _resolve("STORE_GCS_BUCKET", "store.gcs_bucket", "")


def is_gcs_store_enabled() -> bool:
    """True when STORE_GCS_BUCKET is set; enables GCS-backed store (direct object storage)."""
    return bool(STORE_GCS_BUCKET and STORE_GCS_BUCKET.strip())


# =============================================================================
# Validation
# =============================================================================


def _validate_bucket_config():
    """Validate that all required bucket values are set (GCS mode only)."""
    missing = []
    if not RAW_BUCKET:
        missing.append("RAW_BUCKET")
    if not META_BUCKET:
        missing.append("META_BUCKET")
    if not MEMORIES_BUCKET:
        missing.append("MEMORIES_BUCKET")

    if missing:
        _config_logger.critical(
            "Missing required bucket configuration: %s. "
            "Set via environment variables or system config bucket "
            "(SYSTEM_CONFIG_BUCKET). Example: "
            "RAW_BUCKET=myproject-mem-dog-raw-dev "
            "META_BUCKET=myproject-mem-dog-meta-dev "
            "MEMORIES_BUCKET=myproject-mem-dog-memories-dev",
            ", ".join(missing),
        )
        sys.exit(1)


def _validate_ai_bucket_config():
    """Validate that AI bucket values are set (optional feature, GCS only)."""
    missing = []
    if not PROMPTS_BUCKET:
        missing.append("PROMPTS_BUCKET")
    if not EMBEDDINGS_BUCKET:
        missing.append("EMBEDDINGS_BUCKET")
    if not VIEWPOINTS_BUCKET:
        missing.append("VIEWPOINTS_BUCKET")
    if not AI_CONFIG_BUCKET:
        missing.append("AI_CONFIG_BUCKET")
    if not SKILLS_BUCKET:
        missing.append("SKILLS_BUCKET")

    if missing:
        _config_logger.warning(
            "AI Layer buckets not configured: %s. "
            "AI features will be disabled. To enable, set: "
            "PROMPTS_BUCKET, EMBEDDINGS_BUCKET, VIEWPOINTS_BUCKET, AI_CONFIG_BUCKET, SKILLS_BUCKET",
            ", ".join(missing),
        )
        return False
    return True


# =============================================================================
# Feature Flags
# =============================================================================
# In local mode all features are always enabled (subdirectories cost nothing).
# In GCS mode features are enabled only when their bucket is configured.


def is_ai_enabled() -> bool:
    """Check if AI layer is configured and enabled.

    Returns True when STORAGE_BACKEND is ``local`` or ``supabase`` (both
    create all AI stores unconditionally), or when all five AI GCS bucket
    env vars are set.
    """
    if STORAGE_BACKEND in ("local", "supabase"):
        return True
    return bool(PROMPTS_BUCKET and EMBEDDINGS_BUCKET and VIEWPOINTS_BUCKET and AI_CONFIG_BUCKET and SKILLS_BUCKET)


def is_system_ai_available() -> bool:
    """True if AI works without a user-configured API key.

    Covers the system Gemini key and a local/open model server
    (``MODEL_SERVER_URL*``, e.g. host Ollama in lean Docker).
    """
    return bool(SYSTEM_GEMINI_API_KEY) or is_model_server_enabled()


def is_system_gemini_available() -> bool:
    """True when the dedicated system Gemini API key is configured."""
    return bool(SYSTEM_GEMINI_API_KEY)


def is_user_management_enabled() -> bool:
    """Check if user management is configured and enabled.

    Always returns True in local and supabase modes.
    """
    if STORAGE_BACKEND in ("local", "supabase"):
        return True
    return bool(USER_BUCKET)


def is_memories_enabled() -> bool:
    """Check if memory management is configured and enabled.

    Always returns True in local and supabase modes.
    """
    if STORAGE_BACKEND in ("local", "supabase"):
        return True
    return bool(MEMORIES_BUCKET)


def is_sessions_enabled() -> bool:
    """DEPRECATED: Use is_memories_enabled() instead.

    Returns True when memories are enabled (sessions are now a memory sub-type).
    """
    return is_memories_enabled()


def is_stats_enabled() -> bool:
    """Check if statistics feature is configured and enabled.

    Returns True in local and supabase modes, or when STATS_BUCKET is set.
    """
    if STORAGE_BACKEND in ("local", "supabase"):
        return True
    return bool(STATS_BUCKET)


# Only validate bucket config in GCS mode and in production-like environments.
# "dev", "development", "local", and "test" are all treated as non-strict to
# avoid crashing on cold-start timing issues with the system config GCS call.
_NON_STRICT_ENVS = {"dev", "development", "local", "test"}
if STORAGE_BACKEND == "gcs":
    if ENVIRONMENT not in _NON_STRICT_ENVS or os.getenv("VALIDATE_BUCKETS", "").lower() == "true":
        _validate_bucket_config()
        _validate_ai_bucket_config()

# =============================================================================
# Model Server Configuration (Ollama tier URLs)
# =============================================================================

MODEL_SERVER_URL: str = _resolve("MODEL_SERVER_URL", "ai.model_server_url", "").rstrip("/")
MODEL_SERVER_MODEL: str = _resolve("MODEL_SERVER_MODEL", "ai.model_server_model", "gemma")
MODEL_SERVER_TIMEOUT_S: int = int(os.getenv("MODEL_SERVER_TIMEOUT_S", "180"))

# Tier-specific URLs — each points to a dedicated Cloud Run model server.
# Falls back to MODEL_SERVER_URL (medium) when a tier URL is not set.
MODEL_SERVER_URL_SMALL: str = (
    os.getenv("MODEL_SERVER_URL_SMALL", "") or MODEL_SERVER_URL
).rstrip("/")
MODEL_SERVER_URL_MEDIUM: str = (
    os.getenv("MODEL_SERVER_URL_MEDIUM", "") or MODEL_SERVER_URL
).rstrip("/")
MODEL_SERVER_URL_LARGE: str = (
    os.getenv("MODEL_SERVER_URL_LARGE", "") or MODEL_SERVER_URL
).rstrip("/")
MODEL_SERVER_URL_VERY_LARGE: str = (
    os.getenv("MODEL_SERVER_URL_VERY_LARGE", "") or MODEL_SERVER_URL
).rstrip("/")

_TIER_URLS: dict[str, str] = {
    "small":  MODEL_SERVER_URL_SMALL,
    "medium": MODEL_SERVER_URL_MEDIUM,
    "large":  MODEL_SERVER_URL_LARGE,
    "very-large": MODEL_SERVER_URL_VERY_LARGE,
}

_TIER_LABELS: dict[str, str] = {
    "small":  "Gemma 3 1B",
    "medium": "Gemma 3 4B",
    "large":  "Gemma 3 12B",
    "very-large": "Gemma 3 27B",
}


def get_model_server_url(tier: str = "medium") -> str:
    """Return the model server URL for *tier*, falling back to MODEL_SERVER_URL."""
    return _TIER_URLS.get(tier, MODEL_SERVER_URL_MEDIUM) or MODEL_SERVER_URL


def get_model_label(tier: str = "medium") -> str:
    """Return a human-readable model label for *tier*."""
    return _TIER_LABELS.get(tier, "Gemma 3")


def is_model_server_enabled() -> bool:
    """Return True when at least one model server URL is configured."""
    return bool(
        MODEL_SERVER_URL
        or MODEL_SERVER_URL_SMALL
        or MODEL_SERVER_URL_MEDIUM
        or MODEL_SERVER_URL_LARGE
        or MODEL_SERVER_URL_VERY_LARGE
    )


# =============================================================================
# Model Management — deployment mode + storage
# =============================================================================
# DEPLOYMENT_MODE controls how the Models tab activates models:
#   local — docker-compose stack on developer laptop; uses /models volume and
#            Docker socket to restart tier containers.
#   cloud — Cloud Run deployment; updates service env vars via the Cloud Run Admin API.

DEPLOYMENT_MODE: str = os.getenv("DEPLOYMENT_MODE", "local")  # "local" | "cloud"
MODEL_LOCAL_DIR: str = os.getenv("MODEL_LOCAL_DIR", "/models")

# GCS bucket that holds GGUF files (cloud mode).
# Matches the pattern used in deploy-webhook.yml: {PROJECT}-mem-dog-models-{ENV}
GCS_MODELS_BUCKET: str = os.getenv("GCS_MODELS_BUCKET", "")

# Cloud Run deployment metadata (cloud mode).
CLOUD_RUN_REGION: str = os.getenv("CLOUD_RUN_REGION", "us-central1")
GCLOUD_PROJECT: str = os.getenv("GOOGLE_CLOUD_PROJECT", GCP_PROJECT_ID)

# Cloud Run service names for each tier (cloud mode).
MODEL_SERVER_SERVICE_SMALL: str  = os.getenv("MODEL_SERVER_SERVICE_SMALL", "")
MODEL_SERVER_SERVICE_MEDIUM: str = os.getenv("MODEL_SERVER_SERVICE_MEDIUM", "")
MODEL_SERVER_SERVICE_LARGE: str  = os.getenv("MODEL_SERVER_SERVICE_LARGE", "")
MODEL_SERVER_SERVICE_VERY_LARGE: str = os.getenv("MODEL_SERVER_SERVICE_VERY_LARGE", "")

# Docker container names as reported by `docker ps` (local mode).
# docker-compose names containers as <project>-<service>-<index> by default.
DOCKER_SERVICE_SMALL: str  = os.getenv("DOCKER_SERVICE_SMALL",  "mem-dog-model-server-small-1")
DOCKER_SERVICE_MEDIUM: str = os.getenv("DOCKER_SERVICE_MEDIUM", "mem-dog-model-server-medium-1")
DOCKER_SERVICE_LARGE: str  = os.getenv("DOCKER_SERVICE_LARGE",  "mem-dog-model-server-large-1")
DOCKER_SERVICE_VERY_LARGE: str = os.getenv("DOCKER_SERVICE_VERY_LARGE", "mem-dog-model-server-very-large-1")

# Optional HuggingFace token (e.g. for Hugging Face inference API).
HUGGING_FACE_HUB_TOKEN: str = os.getenv("HUGGING_FACE_HUB_TOKEN", os.getenv("HF_TOKEN", ""))

# ---------------------------------------------------------------------------
# Ollama tier (default)
# ---------------------------------------------------------------------------
# Tier model servers are Ollama instances (port 11434). Chat uses
# /v1/chat/completions with explicit model name (from /api/ps or default).
# When False, tiers use legacy model servers (deprecated).
OLLAMA_TIER: bool = os.getenv("OLLAMA_TIER", "true").lower() == "true"

# When True, legacy model management endpoints return 410 Gone. Use Machines tab
# and Ollama proxy endpoints instead. Default false for backward compatibility.
DEPRECATE_OLD_MODEL_MGMT: bool = os.getenv("DEPRECATE_OLD_MODEL_MGMT", "false").lower() == "true"


def get_docker_service_name(tier: str) -> str:
    """Return the Docker container name for a given tier (local mode)."""
    return {
        "small":  DOCKER_SERVICE_SMALL,
        "medium": DOCKER_SERVICE_MEDIUM,
        "large":  DOCKER_SERVICE_LARGE,
        "very-large": DOCKER_SERVICE_VERY_LARGE,
    }.get(tier, DOCKER_SERVICE_MEDIUM)


def get_cloud_run_service_name(tier: str) -> str:
    """Return the Cloud Run service name for a given tier (cloud mode)."""
    return {
        "small":  MODEL_SERVER_SERVICE_SMALL,
        "medium": MODEL_SERVER_SERVICE_MEDIUM,
        "large":  MODEL_SERVER_SERVICE_LARGE,
        "very-large": MODEL_SERVER_SERVICE_VERY_LARGE,
    }.get(tier, MODEL_SERVER_SERVICE_MEDIUM)


# =============================================================================
# Application Configuration
# =============================================================================

# Canonical default user_id (UUID).  This is always the multi-tenancy
# identifier.  The display name / username ("demo") is separate — see
# storage.ensure_default_user().  Never set this to a non-UUID value.
DEFAULT_USER_ID: str = "00000000-0000-0000-0000-000000000001"

# Backward-compat alias — existing code that imports config.DEFAULT_USER
# continues to work.  New code should use DEFAULT_USER_ID.
DEFAULT_USER: str = DEFAULT_USER_ID

# System user for pipeline-level telemetry (OTel spans, webhook processor spans).
SYSTEM_USER_ID = _resolve("SYSTEM_USER_ID", "app.system_user_id", DEFAULT_USER_ID)

# Application version — embedded in telemetry spans and device provenance.
APP_VERSION = _resolve("APP_VERSION", "app.app_version", "0.1.0")

# =============================================================================
# API Base URL (for computing absolute data addresses)
# =============================================================================
# If set, used as the canonical base URL for data addresses in metadata.
# If empty, the address is derived dynamically from the incoming request.
API_BASE_URL = _resolve("API_BASE_URL", "app.api_base_url")


def is_index_enabled() -> bool:
    """True when a dedicated INDEX_BUCKET is configured, or always in local/supabase mode.

    In local mode the index uses a subdirectory of MEM_DOG_DATA_DIR.
    In supabase mode the index is a SupabaseBlobStore.
    In GCS mode an INDEX_BUCKET is optional; when not set, index entries are written
    inside META_BUCKET under the ``_idx/`` prefix.
    """
    return STORAGE_BACKEND in ("local", "supabase") or bool(META_BUCKET)
