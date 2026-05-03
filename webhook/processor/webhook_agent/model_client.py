"""HTTP client for model inference in the webhook agent.

All LLM inference for the payload classifier and the 31 sub-agents routes
through this module.  Model selection is driven by the **API smart routing
config** — the API's ``/api/v1/ai/smart-routing-config/{user_id}`` endpoint
returns per-data-type primary + fallback models.

Inference order (per data type)
-------------------------------
1. **Smart routing primary** — from API routing config (e.g. Ollama Cloud model).
2. **Smart routing fallback** — from API routing config (e.g. Gemini).
3. **Self-hosted model server** — ``MODEL_SERVER_URL_*`` if configured.

Configuration
-------------
``OLLAMA_CLOUD_API_KEY``
    Required for Ollama Cloud models.

``DATA_PIPELINE_AI_FALLBACK_MODEL``
    Gemini model used as fallback (default: gemini/gemini-3.1-pro-preview).

``MODEL_SERVER_URL_SMALL`` / ``MODEL_SERVER_URL_MEDIUM`` / ``MODEL_SERVER_URL``
    URLs of the tiered model servers (Cloud Run).  Last-resort fallback.

Authentication (model server)
------------------------------
All model server services are deployed with ``--no-allow-unauthenticated``.
This module fetches a Google-signed identity token per request and attaches
it as ``Authorization: Bearer <token>``.  Silently omitted locally.
"""

import logging
import os
import threading
import time
from pathlib import Path
from typing import Literal, Optional

# Load shared AI model defaults from config/ai.env (repo root, local dev only).
# Populates GEMINI_MODEL, GEMINI_LITELLM_MODEL, etc. before env lookups below.
try:
    from dotenv import load_dotenv
    _ai_env = Path(__file__).resolve().parents[3] / "config" / "ai.env"
    if _ai_env.exists():
        load_dotenv(_ai_env)
except (ImportError, IndexError):
    pass

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger("mem_dog.webhook.model_client")

# Thread-local storage for last LLM call usage stats
_thread_local = threading.local()


def get_last_usage() -> dict:
    """Return token usage from the most recent LLM call on this thread.

    Returns a dict with keys: prompt_tokens, completion_tokens,
    total_tokens, model, duration_ms.  All default to 0/empty if
    no usage was captured.
    """
    return getattr(_thread_local, "last_usage", {})

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Individual tier URLs.  MODEL_SERVER_URL is the legacy alias for medium.
_URL_SMALL: str = os.environ.get("MODEL_SERVER_URL_SMALL", "").rstrip("/")
_URL_MEDIUM: str = (
    os.environ.get("MODEL_SERVER_URL_MEDIUM")
    or os.environ.get("MODEL_SERVER_URL", "")
).rstrip("/")
_URL_LARGE: str = os.environ.get("MODEL_SERVER_URL_LARGE", "").rstrip("/")
_URL_VERY_LARGE: str = os.environ.get("MODEL_SERVER_URL_VERY_LARGE", "").rstrip("/")

# Expose the medium URL under the legacy name for backward compat.
MODEL_SERVER_URL: str = _URL_MEDIUM
MODEL_SERVER_MODEL: str = os.environ.get("MODEL_SERVER_MODEL", "gemma")

# Data processing pipeline AI: Ollama Cloud primary (per-tier), Gemini fallback.
DATA_PIPELINE_AI_PRIMARY_MODEL: str = os.environ.get(
    "DATA_PIPELINE_AI_PRIMARY_MODEL",
    os.environ.get("GEMINI_LITELLM_MODEL", os.environ.get("GEMINI_MODEL", "gemini/gemini-3.1-pro-preview")),
)
DATA_PIPELINE_AI_FALLBACK_MODEL: str = os.environ.get(
    "DATA_PIPELINE_AI_FALLBACK_MODEL",
    os.environ.get("FALLBACK_LITELLM_MODEL", "gemini/gemini-3.1-pro-preview"),
)
DATA_PIPELINE_AI_FALLBACK_ENABLED: bool = os.environ.get(
    "DATA_PIPELINE_AI_FALLBACK_ENABLED", "true"
).lower() in ("1", "true", "yes")
OLLAMA_CLOUD_API_KEY: str = os.environ.get("OLLAMA_CLOUD_API_KEY", "") or os.environ.get(
    "OLLAMA_API_KEY", ""
)
OLLAMA_CLOUD_API_BASE: str = os.environ.get("OLLAMA_CLOUD_API_BASE", "https://api.ollama.com")


# Timeout for a single inference request.
# CPU inference on a 12B model can take 60-180 s; Gemini is typically <5 s.
_INFERENCE_TIMEOUT_S: int = int(os.environ.get("MODEL_SERVER_TIMEOUT_S", "180"))

ModelTier = Literal["small", "medium", "large", "very-large"]

def _resolve_url(tier: ModelTier) -> str:
    """Return the best available model server URL for *tier*.

    Falls back through small → medium → large → very-large until a non-empty URL is found.
    Returns an empty string if none is configured (triggers Gemini fallback).
    """
    if tier == "small":
        return _URL_SMALL or _URL_MEDIUM or _URL_LARGE or _URL_VERY_LARGE
    if tier == "large":
        return _URL_LARGE or _URL_MEDIUM or _URL_SMALL or _URL_VERY_LARGE
    if tier == "very-large":
        return _URL_VERY_LARGE or _URL_LARGE or _URL_MEDIUM or _URL_SMALL
    return _URL_MEDIUM or _URL_SMALL or _URL_LARGE or _URL_VERY_LARGE

# ---------------------------------------------------------------------------
# HTTP session with retry
# ---------------------------------------------------------------------------

_RETRY = Retry(
    total=3,
    connect=3,
    read=2,
    backoff_factor=0.5,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=frozenset(["POST"]),
    raise_on_status=False,
)
_session = requests.Session()
_adapter = HTTPAdapter(max_retries=_RETRY)
_session.mount("https://", _adapter)
_session.mount("http://", _adapter)

# ---------------------------------------------------------------------------
# Identity token (Cloud Run service-to-service auth)
# ---------------------------------------------------------------------------

def _identity_token(audience: str) -> Optional[str]:
    """Fetch a GCP identity token for Cloud Run private invocation.

    Returns ``None`` when running locally (no metadata server), in which case
    no ``Authorization`` header is sent.

    Args:
        audience: The model server base URL (used as the token audience).

    Returns:
        Signed ID token string, or ``None`` on failure.
    """
    try:
        import google.auth.transport.requests as google_requests
        import google.oauth2.id_token
        auth_req = google_requests.Request()
        return google.oauth2.id_token.fetch_id_token(auth_req, audience)
    except Exception as exc:
        logger.debug("Could not fetch identity token (running locally?): %s", exc)
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _chat_model_server(
    messages: list[dict],
    max_tokens: int,
    temperature: float,
    url: str,
    tier: str,
) -> str:
    """Call the Ollama model server (OpenAI-compatible API)."""
    token = _identity_token(url)
    headers: dict = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    payload = {
        "model": MODEL_SERVER_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    logger.info(
        "Model server request | tier=%s  messages=%d  max_tokens=%d  temperature=%.1f",
        tier, len(messages), max_tokens, temperature,
    )
    logger.debug("Model server messages | %s", messages)

    t0 = time.monotonic()
    resp = _session.post(
        f"{url}/v1/chat/completions",
        json=payload,
        headers=headers,
        timeout=_INFERENCE_TIMEOUT_S,
    )
    duration_ms = (time.monotonic() - t0) * 1000
    resp.raise_for_status()

    body = resp.json()
    raw_content = body["choices"][0]["message"]["content"]
    result: str = (raw_content or "").strip()

    # Capture token usage
    usage = body.get("usage", {})
    _thread_local.last_usage = {
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
        "total_tokens": usage.get("total_tokens", 0),
        "model": MODEL_SERVER_MODEL,
        "duration_ms": round(duration_ms, 1),
    }

    logger.info("Model server response | tier=%s  chars=%d", tier, len(result))
    logger.debug("Model server response text | %s", result)
    return result


def _chat_litellm(
    model: str,
    messages: list[dict],
    max_tokens: int,
    temperature: float,
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
) -> str:
    """Call LiteLLM completion with the given model (e.g. gemini/..., ollama/...)."""
    try:
        import litellm
    except ImportError as exc:
        raise RuntimeError(
            "litellm is not installed.  Add it to requirements.txt."
        ) from exc

    logger.info(
        "LiteLLM request | model=%s  messages=%d  max_tokens=%d  temperature=%.1f",
        model, len(messages), max_tokens, temperature,
    )
    logger.debug("LiteLLM messages | %s", messages)

    kwargs: dict = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    # Skip max_tokens for Ollama Cloud — let the model use its own default.
    if not model.startswith("ollama/"):
        kwargs["max_tokens"] = max_tokens
    if api_key:
        kwargs["api_key"] = api_key
    if api_base:
        kwargs["api_base"] = api_base

    t0 = time.monotonic()
    response = litellm.completion(**kwargs)
    duration_ms = (time.monotonic() - t0) * 1000
    raw_content = response.choices[0].message.content
    result: str = (raw_content or "").strip()

    # Capture token usage
    usage = getattr(response, "usage", None)
    if usage:
        _thread_local.last_usage = {
            "prompt_tokens": getattr(usage, "prompt_tokens", 0) or 0,
            "completion_tokens": getattr(usage, "completion_tokens", 0) or 0,
            "total_tokens": getattr(usage, "total_tokens", 0) or 0,
            "model": model,
            "duration_ms": round(duration_ms, 1),
        }
    else:
        _thread_local.last_usage = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "model": model,
            "duration_ms": round(duration_ms, 1),
        }

    logger.info("LiteLLM response | model=%s  chars=%d", model, len(result))
    logger.debug("LiteLLM response text | %s", result)
    return result


# ---------------------------------------------------------------------------
# Per-data-type smart routing (centralized via API merged config)
# ---------------------------------------------------------------------------


def _normalize_model_prefix(model: str) -> str:
    """Ensure model has the correct LiteLLM prefix (ollama/ or gemini/)."""
    if model.startswith(("ollama/", "gemini/", "openai/", "anthropic/", "openrouter/", "together_ai/", "huggingface/", "bedrock/")):
        return model
    # Bare model names (e.g. "gemma3:27b") default to ollama/
    return f"ollama/{model}"


def _get_routing_config(user_id: str) -> dict[str, dict]:
    """Fetch merged routing config from the API, cached via AIClient (5 min TTL).

    Returns ``{agent_type → {primary, fallback, ...}}`` or ``{}`` on error.
    """
    try:
        from .api_client import ai_client
        return ai_client.get_smart_routing_config(user_id)
    except Exception as exc:
        logger.debug("Could not fetch routing config for user %s: %s", user_id, exc)
        return {}


def _resolve_credentials(model: str, user_id: str | None) -> dict:
    """Resolve API key and base URL for a model.

    Fallback chain:
    1. User-configured engine credentials (from Model Garden via API)
    2. Environment variables (OLLAMA_CLOUD_API_KEY, etc.)
    3. Empty dict (no credentials)
    """
    # Determine provider from model prefix
    provider_map = {
        "ollama/": "ollama",
        "gemini/": "gemini",
        "openai/": "openai",
        "anthropic/": "anthropic",
        "openrouter/": "openrouter",
        "together_ai/": "together",
        "huggingface/": "huggingface",
        "bedrock/": "bedrock",
    }

    engine_type = None
    for prefix, etype in provider_map.items():
        if model.startswith(prefix):
            engine_type = etype
            break

    # Try user-configured credentials
    # For ollama models, also check ollama_cloud engine type
    engine_types_to_try = [engine_type] if engine_type else []
    if engine_type == "ollama":
        engine_types_to_try.append("ollama_cloud")

    if user_id and engine_types_to_try:
        try:
            from .api_client import ai_client
            for etype in engine_types_to_try:
                creds = ai_client.get_engine_credentials(user_id, etype)
                if creds and creds.get("api_key"):
                    result: dict = {"api_key": creds["api_key"]}
                    if creds.get("base_url"):
                        result["api_base"] = creds["base_url"]
                    return result
        except Exception as exc:
            logger.debug("Could not resolve user credentials for %s/%s: %s", user_id, engine_type, exc)

    # Fallback to env vars
    if engine_type == "ollama" or (not engine_type and model.startswith("ollama/")):
        if OLLAMA_CLOUD_API_KEY:
            return {"api_key": OLLAMA_CLOUD_API_KEY, "api_base": OLLAMA_CLOUD_API_BASE}

    return {}


def chat_for_data_type(
    messages: list[dict],
    agent_type: str,
    user_id: Optional[str] = None,
    max_tokens: int = 256,
    temperature: float = 0.3,
) -> str:
    """Route inference using the API's merged routing config.

    Fallback chain:
    1. API routing config → ``routing[agent_type]["primary"]``
    2. API routing config → ``routing[agent_type]["fallback"]``
    3. Self-hosted model server (``MODEL_SERVER_URL_*``) if configured.

    Args:
        messages: OpenAI-style message list.
        agent_type: The sub-agent data type (e.g. ``"json"``, ``"image"``).
        user_id: Owner user ID for preference lookup.
        max_tokens: Maximum tokens to generate.
        temperature: Sampling temperature.

    Returns:
        The generated text string.
    """
    routing = _get_routing_config(user_id) if user_id and agent_type else {}
    entry = routing.get(agent_type, {})
    primary_model = entry.get("primary", "")
    fallback_model = entry.get("fallback", "")
    logger.info(
        "Smart routing config | agent_type=%s  primary=%s  fallback=%s  user=%s",
        agent_type, primary_model or "(none)", fallback_model or "(none)", user_id,
    )

    # 1. Try primary model from routing config
    if primary_model:
        model = _normalize_model_prefix(primary_model)
        kwargs = _resolve_credentials(model, user_id)

        try:
            logger.info(
                "Smart routing primary | agent_type=%s  model=%s  max_tokens=%d",
                agent_type, model, max_tokens,
            )
            return _chat_litellm(model, messages, max_tokens, temperature, **kwargs)
        except Exception as exc:
            logger.warning(
                "Smart routing primary failed | agent_type=%s  model=%s  error=%s",
                agent_type, model, exc,
            )

    # 2. Try fallback model from routing config
    if fallback_model:
        fb_model = _normalize_model_prefix(fallback_model)
        fb_kwargs = _resolve_credentials(fb_model, user_id)
        try:
            logger.info(
                "Smart routing fallback | agent_type=%s  model=%s",
                agent_type, fb_model,
            )
            return _chat_litellm(fb_model, messages, max_tokens, temperature, **fb_kwargs)
        except Exception as fb_exc:
            logger.warning("Smart routing fallback failed | agent_type=%s  error=%s", agent_type, fb_exc)

    # 3. Last resort: self-hosted model server
    url = _resolve_url("medium")
    if url:
        logger.info("Falling back to self-hosted model server | agent_type=%s", agent_type)
        return _chat_model_server(messages, max_tokens, temperature, url, "medium")

    raise RuntimeError(
        f"No model available for agent_type={agent_type}: "
        "routing config returned no models and no MODEL_SERVER_URL is configured"
    )


def chat_multimodal_for_data_type(
    messages: list[dict],
    agent_type: str,
    user_id: Optional[str] = None,
    max_tokens: int = 1024,
    temperature: float = 0.3,
    mime_type: str = "",
) -> str:
    """Multimodal inference with centralized routing config.

    Smart routing provides per-data-type model selection:
    - Audio/video → omni model (native audio+video)
    - Image/PDF   → vision model
    Non-VL Ollama models (gemma3 etc.) are skipped for multimodal.
    Falls back to routing fallback model, then self-hosted model server.
    """
    routing = _get_routing_config(user_id) if user_id and agent_type else {}
    entry = routing.get(agent_type, {})
    primary_model = entry.get("primary", "")
    fallback_model = entry.get("fallback", "")

    # 1. Try primary from routing config (if vision-capable)
    if primary_model:
        model = _normalize_model_prefix(primary_model)
        is_ollama = model.startswith("ollama/")
        model_lower = model.lower()
        is_vision_capable = not is_ollama or "-vl" in model_lower or "llava" in model_lower or "qwen3.5" in model_lower

        if is_ollama and not is_vision_capable:
            logger.info(
                "Smart routing multimodal | agent_type=%s  skipping %s (no vision support)",
                agent_type, model,
            )
        else:
            kwargs = _resolve_credentials(model, user_id)
            try:
                logger.info(
                    "Smart routing multimodal | agent_type=%s  model=%s",
                    agent_type, model,
                )
                return _chat_litellm(model, messages, max_tokens, temperature, **kwargs)
            except Exception as exc:
                logger.warning(
                    "Smart routing multimodal failed | agent_type=%s  error=%s",
                    agent_type, exc,
                )

    # 2. Try fallback from routing config
    if fallback_model:
        fb_model = _normalize_model_prefix(fallback_model)
        fb_kwargs = _resolve_credentials(fb_model, user_id)
        try:
            logger.info("Smart routing multimodal fallback | agent_type=%s  model=%s", agent_type, fb_model)
            return _chat_litellm(fb_model, messages, max_tokens, temperature, **fb_kwargs)
        except Exception as exc:
            logger.warning("Smart routing multimodal fallback failed | agent_type=%s  error=%s", agent_type, exc)

    # 3. Last resort: self-hosted model server
    url = _resolve_url("medium")
    if url:
        logger.info("Multimodal falling back to self-hosted model server | agent_type=%s", agent_type)
        return _chat_model_server(messages, max_tokens, temperature, url, "medium")

    raise RuntimeError(
        f"No multimodal model available for agent_type={agent_type}: "
        "routing config returned no models and no MODEL_SERVER_URL is configured"
    )


