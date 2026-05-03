"""Configuration for Webhook Gateway.

All settings are resolved from environment variables.  When ``python-dotenv``
is installed the ``.env`` file in the package root is loaded automatically.
"""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

# Load shared AI model defaults from config/ai.env (repo root), then local .env.
_repo_root = Path(__file__).resolve().parent.parent.parent
load_dotenv(_repo_root / "config" / "ai.env")

_gateway_dir = Path(__file__).resolve().parent.parent
load_dotenv(_gateway_dir / ".env")

_log = logging.getLogger("webhook_gateway.config")

# ---------------------------------------------------------------------------
# LLM provider configuration
# ---------------------------------------------------------------------------
# LLM_PROVIDER selects the backend.  "gemini" (default) uses the native
# google-genai SDK.  Any other value routes through litellm, which supports
# 100+ providers: openai, anthropic, openrouter, mistral, bedrock, ollama,
# together_ai, cloudflare, nvidia_nim, vllm, huggingface, etc.
# See https://docs.openclaw.ai/providers for the full list.
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "gemini")

# Model identifier.  For native Gemini this is the bare model name.
# For litellm providers use the litellm model format, e.g.:
#   openai/gpt-4o, anthropic/claude-sonnet-4-20250514, ollama/llama3,
#   mistral/mistral-large-latest, together_ai/meta-llama/Llama-3-70b, etc.
# When LLM_PROVIDER != "gemini" and LLM_MODEL does not contain a "/",
# the provider is prepended automatically (e.g. "gpt-4o" → "openai/gpt-4o").
LLM_MODEL: str = os.getenv("LLM_MODEL", "")

# Backward-compatible Gemini-specific env vars
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.1-pro-preview")  # default from ai.env

# Generic LLM API key — used by litellm when the provider-specific env var
# is not set (e.g. OPENAI_API_KEY, ANTHROPIC_API_KEY).
LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")

# Optional base URL override for litellm (useful for self-hosted endpoints,
# Ollama, vLLM, LiteLLM proxy, etc.)
LLM_API_BASE: str = os.getenv("LLM_API_BASE", "")

# Temperature and token limits (apply to all providers)
LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.1"))
LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "512"))


def get_effective_model() -> str:
    """Return the litellm-style model string for the active provider."""
    if LLM_PROVIDER == "gemini":
        return LLM_MODEL or GEMINI_MODEL
    model = LLM_MODEL or GEMINI_MODEL
    if "/" not in model:
        return f"{LLM_PROVIDER}/{model}"
    return model


def has_llm_configured() -> bool:
    """Return True if any LLM provider is usable."""
    if LLM_PROVIDER == "gemini":
        return bool(GEMINI_API_KEY)
    if LLM_API_KEY:
        return True
    provider_key_map = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "mistral": "MISTRAL_API_KEY",
        "together_ai": "TOGETHERAI_API_KEY",
        "bedrock": "AWS_ACCESS_KEY_ID",
        "cloudflare": "CLOUDFLARE_API_KEY",
        "nvidia_nim": "NVIDIA_API_KEY",
        "huggingface": "HUGGINGFACE_API_KEY",
    }
    env_name = provider_key_map.get(LLM_PROVIDER)
    if env_name and os.getenv(env_name):
        return True
    # Ollama / vLLM / local endpoints don't require an API key
    if LLM_PROVIDER in ("ollama", "vllm") or LLM_API_BASE:
        return True
    return False


# ---------------------------------------------------------------------------
# Existing memdog webhook API gateway
# ---------------------------------------------------------------------------
WEBHOOK_GATEWAY_URL: str = os.getenv("WEBHOOK_GATEWAY_URL", "")
WEBHOOK_API_KEY: str = os.getenv("WEBHOOK_API_KEY", "")

# ---------------------------------------------------------------------------
# memdog API service
# ---------------------------------------------------------------------------
MEM_DOG_API_URL: str = os.getenv("MEM_DOG_API_URL", "").rstrip("/")
MEM_DOG_API_KEY: str = os.getenv("MEM_DOG_API_KEY", "")

# GKE pipeline routing — used when ?pipeline=gke is passed
MEM_DOG_API_GKE_URL: str = os.getenv("MEM_DOG_API_GKE_URL", "").rstrip("/")
WEBHOOK_GKE_RECEIVER_URL: str = os.getenv("WEBHOOK_GKE_RECEIVER_URL", "").rstrip("/")


def get_api_url(pipeline: str | None = None) -> str:
    """Return the API URL for the given pipeline, falling back to default."""
    if pipeline == "gke" and MEM_DOG_API_GKE_URL:
        return MEM_DOG_API_GKE_URL
    return MEM_DOG_API_URL


def get_webhook_url(pipeline: str | None = None) -> str:
    """Return the webhook receiver URL for the given pipeline."""
    if pipeline == "gke" and WEBHOOK_GKE_RECEIVER_URL:
        return WEBHOOK_GKE_RECEIVER_URL
    return WEBHOOK_GATEWAY_URL

# ---------------------------------------------------------------------------
# Direct Supabase read access (optional — OC-Read pattern)
# ---------------------------------------------------------------------------
# When both are set, high-frequency reads (identity lookups, memory checks,
# channel config) go directly to Supabase, bypassing the memdog API.
# All writes still go through the API.  Falls back to API-only when unset.
SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "") or os.getenv("SUPABASE_KEY", "")

# Publish every inbound message as a memory record in the memdog API.
# Runs regardless of LLM configuration.  Set to "false" to disable.
PUBLISH_TO_MEMORY: bool = os.getenv("PUBLISH_TO_MEMORY", "true").lower() == "true"

# ---------------------------------------------------------------------------
# OTEL telemetry
# ---------------------------------------------------------------------------
OTEL_ENABLED: bool = os.getenv("OTEL_ENABLED", "true").lower() == "true"
OTEL_SERVICE_NAME: str = os.getenv("OTEL_SERVICE_NAME", "webhook-gateway")
OTEL_EXPORTER_OTLP_ENDPOINT: str = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
OTEL_EXPORTER_OTLP_PROTOCOL: str = os.getenv("OTEL_EXPORTER_OTLP_PROTOCOL", "grpc")

# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------
# API key protecting inbound endpoints. When set, all webhook/query/channel
# requests must include it as ``Authorization: Bearer <key>``,
# ``x-api-key`` header, or ``?api_key=`` query parameter.
# Leave empty to run in open mode (not recommended for production).
WGW_API_KEY: str = os.getenv("WGW_API_KEY", "")

# Comma-separated list of allowed client IPs (empty = allow all).
WGW_ALLOWED_IPS: set[str] = {
    ip.strip() for ip in os.getenv("WGW_ALLOWED_IPS", "").split(",") if ip.strip()
}

# Requests per minute per IP (0 = no limit).
WGW_RATE_LIMIT: int = int(os.getenv("WGW_RATE_LIMIT", "0"))

# Comma-separated CORS origins (empty = allow all; use for production).
WGW_CORS_ORIGINS: list[str] = [
    o.strip() for o in os.getenv("WGW_CORS_ORIGINS", "").split(",") if o.strip()
]

# ---------------------------------------------------------------------------
# Zoom WebSocket (Server-to-Server OAuth)
# ---------------------------------------------------------------------------
ZOOM_WS_ENABLED: bool = os.getenv("ZOOM_WS_ENABLED", "false").lower() == "true"
ZOOM_CLIENT_ID: str = os.getenv("ZOOM_CLIENT_ID", "")
ZOOM_CLIENT_SECRET: str = os.getenv("ZOOM_CLIENT_SECRET", "")
ZOOM_ACCOUNT_ID: str = os.getenv("ZOOM_ACCOUNT_ID", "")
ZOOM_SUBSCRIPTION_ID: str = os.getenv("ZOOM_SUBSCRIPTION_ID", "")

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
DEFAULT_USER_ID: str = os.getenv("DEFAULT_USER_ID", "00000000-0000-0000-0000-000000000001")
PORT: int = int(os.getenv("PORT", "8080"))
MAX_PAYLOAD_BYTES: int = int(os.getenv("MAX_PAYLOAD_BYTES", str(10_485_760)))  # 10 MB

_log.info(
    "Webhook Gateway config loaded | provider=%s model=%s otel=%s webhook_gw=%s api=%s",
    LLM_PROVIDER,
    get_effective_model(),
    OTEL_ENABLED,
    WEBHOOK_GATEWAY_URL[:40] + "..." if len(WEBHOOK_GATEWAY_URL) > 40 else WEBHOOK_GATEWAY_URL,
    MEM_DOG_API_URL[:40] + "..." if len(MEM_DOG_API_URL) > 40 else MEM_DOG_API_URL,
)
