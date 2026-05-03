"""Smart model routing — Ollama Cloud model cards + per-data-type suggestion engine.

Fetches available models from the Ollama Cloud API, enriches them with
capability metadata from :mod:`model_catalog`, and suggests optimal
primary + fallback models for each data type based on declared requirements.

Users can override suggestions via ``smart_routing_overrides`` in their
AI preferences; the webhook agent's :func:`model_client.chat_for_data_type`
reads those overrides at inference time.
"""

import logging
import time
from typing import Any, Optional

import requests

from app import config
from app import model_catalog

logger = logging.getLogger("mem_dog.smart_routing")

# ---------------------------------------------------------------------------
# In-memory cache for Ollama Cloud model list
# ---------------------------------------------------------------------------

_model_cache: dict[str, Any] = {"models": [], "fetched_at": 0.0}
_CACHE_TTL_S = 3600  # 1 hour


# ---------------------------------------------------------------------------
# Tier ordering (for comparisons)
# ---------------------------------------------------------------------------

_TIER_ORDER = {"small": 0, "medium": 1, "large": 2, "very-large": 3}


def _tier_rank(tier: str) -> int:
    return _TIER_ORDER.get(tier, 1)


# ---------------------------------------------------------------------------
# Data type requirements
# ---------------------------------------------------------------------------

DATA_TYPE_REQUIREMENTS: dict[str, dict[str, Any]] = {
    "json":              {"min_tier": "small",  "needs": ["structured_output"]},
    "csv":               {"min_tier": "small",  "needs": ["structured_output"]},
    "yaml":              {"min_tier": "small",  "needs": ["structured_output"]},
    "xml":               {"min_tier": "small",  "needs": ["structured_output"]},
    "sensor":            {"min_tier": "small",  "needs": []},
    "gps":               {"min_tier": "small",  "needs": []},
    "biometric":         {"min_tier": "small",  "needs": []},
    "iot_sensor":        {"min_tier": "small",  "needs": []},
    "archive":           {"min_tier": "small",  "needs": []},
    "binary_blob":       {"min_tier": "small",  "needs": []},
    "feed":              {"min_tier": "small",  "needs": []},
    "log_stream":        {"min_tier": "small",  "needs": []},
    "log_file":          {"min_tier": "small",  "needs": []},
    "time_series":       {"min_tier": "small",  "needs": []},
    "code":              {"min_tier": "medium", "needs": ["code"]},
    "email":             {"min_tier": "medium", "needs": []},
    "chat":              {"min_tier": "medium", "needs": []},
    "channel_message":   {"min_tier": "medium", "needs": []},
    "calendar":          {"min_tier": "medium", "needs": ["structured_output"]},
    "financial":         {"min_tier": "medium", "needs": ["structured_output"]},
    "industrial":        {"min_tier": "medium", "needs": []},
    "vehicle_telemetry": {"min_tier": "medium", "needs": []},
    "infrastructure":    {"min_tier": "medium", "needs": []},
    "markdown":          {"min_tier": "medium", "needs": []},
    "html_doc":          {"min_tier": "medium", "needs": []},
    "pdf":               {"min_tier": "large",  "needs": ["long_context"]},
    "office_doc":        {"min_tier": "large",  "needs": ["long_context"]},
    "web_page":          {"min_tier": "large",  "needs": ["long_context"]},
    "scientific":        {"min_tier": "large",  "needs": ["reasoning"]},
    "satellite":         {"min_tier": "large",  "needs": []},
    "geospatial":        {"min_tier": "large",  "needs": []},
    "lidar":             {"min_tier": "large",  "needs": []},
    "model_3d":          {"min_tier": "large",  "needs": []},
    "medical_imaging":   {"min_tier": "large",  "needs": ["multimodal"]},
    "conferencing":      {"min_tier": "large",  "needs": ["long_context"]},
    "image":             {"min_tier": "large",  "needs": ["multimodal"]},
    "image_batch":       {"min_tier": "large",  "needs": ["multimodal"]},
    "video_url":         {"min_tier": "large",  "needs": ["multimodal"]},
    "video_stream":      {"min_tier": "large",  "needs": ["multimodal"]},
    "audio_url":         {"min_tier": "large",  "needs": ["multimodal"]},
    "audio_stream":      {"min_tier": "large",  "needs": ["multimodal"]},
}

# Data type groupings for the UI
DATA_TYPE_CATEGORIES: dict[str, list[str]] = {
    "Structured": ["json", "csv", "yaml", "xml", "calendar", "financial"],
    "Sensor / IoT": ["sensor", "gps", "biometric", "iot_sensor", "time_series"],
    "Documents": ["pdf", "office_doc", "markdown", "html_doc", "web_page", "scientific"],
    "Media": ["image", "image_batch", "video_url", "video_stream", "audio_url", "audio_stream"],
    "Communications": ["email", "chat", "channel_message", "conferencing"],
    "Code & Logs": ["code", "log_stream", "log_file", "feed"],
    "Spatial & Binary": ["satellite", "geospatial", "lidar", "model_3d", "medical_imaging",
                         "archive", "binary_blob"],
    "Industrial": ["industrial", "vehicle_telemetry", "infrastructure"],
}


# ---------------------------------------------------------------------------
# Capability inference from model name / size
# ---------------------------------------------------------------------------

# Known capabilities by model name patterns
_MODEL_CAPABILITIES: dict[str, dict[str, Any]] = {
    "phi3:mini":             {"tier": "small",  "multimodal": False, "structured_output": True,  "code": False, "long_context": False, "reasoning": False, "param_b": 3.8},
    "gemma3:4b":             {"tier": "small",  "multimodal": False, "structured_output": True,  "code": False, "long_context": False, "reasoning": False, "param_b": 4},
    "gemma3:12b":            {"tier": "medium", "multimodal": False, "structured_output": True,  "code": True,  "long_context": False, "reasoning": False, "param_b": 12},
    "gemma3:27b":            {"tier": "large",  "multimodal": False, "structured_output": True,  "code": True,  "long_context": True,  "reasoning": True,  "param_b": 27},
    "ministral-3:3b":        {"tier": "small",  "multimodal": False, "structured_output": True,  "code": False, "long_context": False, "reasoning": False, "param_b": 3},
    "ministral-3:8b":        {"tier": "small",  "multimodal": False, "structured_output": True,  "code": False, "long_context": False, "reasoning": False, "param_b": 8},
    "ministral-3:14b":       {"tier": "medium", "multimodal": False, "structured_output": True,  "code": True,  "long_context": False, "reasoning": False, "param_b": 14},
    "qwen3-vl:235b":         {"tier": "large",  "multimodal": True,  "structured_output": True,  "code": True,  "long_context": True,  "reasoning": True,  "param_b": 235},
    "qwen3-vl:235b-instruct":{"tier": "large",  "multimodal": True,  "structured_output": True,  "code": True,  "long_context": True,  "reasoning": True,  "param_b": 235},
    "qwen3.5:397b":          {"tier": "large",  "multimodal": False, "structured_output": True,  "code": True,  "long_context": True,  "reasoning": True,  "param_b": 397},
    "qwen3-next:80b":        {"tier": "large",  "multimodal": False, "structured_output": True,  "code": True,  "long_context": True,  "reasoning": True,  "param_b": 80},
    "deepseek-v3.1:671b":    {"tier": "large",  "multimodal": False, "structured_output": True,  "code": True,  "long_context": True,  "reasoning": True,  "param_b": 671},
    "deepseek-v3.2":         {"tier": "large",  "multimodal": False, "structured_output": True,  "code": True,  "long_context": True,  "reasoning": True,  "param_b": 671},
    "mistral-large-3:675b":  {"tier": "large",  "multimodal": False, "structured_output": True,  "code": True,  "long_context": True,  "reasoning": True,  "param_b": 675},
    "kimi-k2.5":             {"tier": "large",  "multimodal": False, "structured_output": True,  "code": True,  "long_context": True,  "reasoning": True,  "param_b": 500},
    "kimi-k2:1t":            {"tier": "large",  "multimodal": False, "structured_output": True,  "code": True,  "long_context": True,  "reasoning": True,  "param_b": 1000},
    "minimax-m2":            {"tier": "large",  "multimodal": False, "structured_output": True,  "code": True,  "long_context": True,  "reasoning": True,  "param_b": 400},
    "minimax-m2.1":          {"tier": "large",  "multimodal": False, "structured_output": True,  "code": True,  "long_context": True,  "reasoning": True,  "param_b": 400},
    "minimax-m2.5":          {"tier": "large",  "multimodal": False, "structured_output": True,  "code": True,  "long_context": True,  "reasoning": True,  "param_b": 400},
    "glm-4.6":               {"tier": "large",  "multimodal": False, "structured_output": True,  "code": True,  "long_context": True,  "reasoning": True,  "param_b": 200},
    "glm-4.7":               {"tier": "large",  "multimodal": False, "structured_output": True,  "code": True,  "long_context": True,  "reasoning": True,  "param_b": 200},
    "glm-5":                 {"tier": "large",  "multimodal": False, "structured_output": True,  "code": True,  "long_context": True,  "reasoning": True,  "param_b": 200},
    "gpt-oss:20b":           {"tier": "medium", "multimodal": False, "structured_output": True,  "code": True,  "long_context": False, "reasoning": False, "param_b": 20},
    "gpt-oss:120b":          {"tier": "large",  "multimodal": False, "structured_output": True,  "code": True,  "long_context": True,  "reasoning": True,  "param_b": 120},
    "cogito-2.1:671b":       {"tier": "large",  "multimodal": False, "structured_output": True,  "code": True,  "long_context": True,  "reasoning": True,  "param_b": 671},
    "devstral-2:123b":       {"tier": "large",  "multimodal": False, "structured_output": True,  "code": True,  "long_context": True,  "reasoning": False, "param_b": 123},
    "devstral-small-2:24b":  {"tier": "medium", "multimodal": False, "structured_output": True,  "code": True,  "long_context": False, "reasoning": False, "param_b": 24},
    "nemotron-3-nano:30b":   {"tier": "medium", "multimodal": False, "structured_output": True,  "code": True,  "long_context": False, "reasoning": False, "param_b": 30},
    "rnj-1:8b":              {"tier": "small",  "multimodal": False, "structured_output": True,  "code": False, "long_context": False, "reasoning": False, "param_b": 8},
    "qwen3-coder-next":      {"tier": "large",  "multimodal": False, "structured_output": True,  "code": True,  "long_context": True,  "reasoning": False, "param_b": 200},
    "qwen3-coder:480b":      {"tier": "large",  "multimodal": False, "structured_output": True,  "code": True,  "long_context": True,  "reasoning": False, "param_b": 480},
    "gemini-3-flash-preview": {"tier": "large", "multimodal": True,  "structured_output": True,  "code": True,  "long_context": True,  "reasoning": True,  "param_b": 0},
}


def _infer_capabilities(model_name: str) -> dict[str, Any]:
    """Infer model capabilities from name, falling back to heuristics."""
    # Exact match
    if model_name in _MODEL_CAPABILITIES:
        return dict(_MODEL_CAPABILITIES[model_name])

    # Try without tag (e.g. "deepseek-v3.2" might not have a size suffix)
    base = model_name.split(":")[0] if ":" in model_name else model_name
    if base in _MODEL_CAPABILITIES:
        return dict(_MODEL_CAPABILITIES[base])

    # Heuristic: parse param size from name
    param_b = 0
    for part in model_name.replace("-", ":").split(":"):
        part_lower = part.lower().rstrip("b")
        try:
            param_b = float(part_lower)
        except ValueError:
            continue

    if param_b > 100:
        tier = "large"
    elif param_b > 10:
        tier = "medium"
    else:
        tier = "small"

    is_vision = any(kw in model_name.lower() for kw in ("vl", "vision", "multimodal"))
    is_code = any(kw in model_name.lower() for kw in ("code", "coder", "devstral"))

    return {
        "tier": tier,
        "multimodal": is_vision,
        "structured_output": True,
        "code": is_code or param_b > 10,
        "long_context": param_b > 20,
        "reasoning": param_b > 50,
        "param_b": param_b,
    }


# ---------------------------------------------------------------------------
# Enrichment — cross-reference with model_catalog
# ---------------------------------------------------------------------------

def enrich_model_card(model: dict) -> dict:
    """Enrich a raw Ollama Cloud model entry with capability metadata.

    Args:
        model: Dict with at least ``"name"`` from the Ollama tags API.

    Returns:
        Enriched dict with capabilities, tier, best_for, etc.
    """
    name = model.get("name", "")
    caps = _infer_capabilities(name)

    # Cross-reference with self-hostable catalog for extra metadata
    catalog_match = None
    for _mid, entry in model_catalog.SELF_HOSTABLE_MODELS.items():
        if name.startswith(entry.get("family", "---")):
            catalog_match = entry
            break

    # Prefix with ollama/ for consistent LiteLLM provider format
    display_name = f"ollama/{name}" if not name.startswith(("ollama/", "gemini/", "openai/")) else name

    enriched = {
        "name": display_name,
        "size": model.get("size", 0),
        "modified_at": model.get("modified_at", ""),
        "digest": model.get("digest", ""),
        # Capabilities
        "tier": caps.get("tier", "medium"),
        "param_b": caps.get("param_b", 0),
        "multimodal": caps.get("multimodal", False),
        "structured_output": caps.get("structured_output", True),
        "code": caps.get("code", False),
        "long_context": caps.get("long_context", False),
        "reasoning": caps.get("reasoning", False),
    }

    if catalog_match:
        enriched["context_window"] = catalog_match.get("context_window", 0)
        enriched["best_for"] = catalog_match.get("best_for", [])
        enriched["benchmark_scores"] = catalog_match.get("benchmark_scores", {})
    else:
        enriched["context_window"] = 128000 if caps.get("long_context") else 32768
        enriched["best_for"] = []
        enriched["benchmark_scores"] = {}

    return enriched


# ---------------------------------------------------------------------------
# Ollama Cloud model fetcher
# ---------------------------------------------------------------------------

def fetch_ollama_cloud_models(refresh: bool = False) -> list[dict]:
    """Fetch available models from Ollama Cloud API.

    Results are cached in-memory for 1 hour. Pass ``refresh=True`` to
    force a re-fetch.

    Returns:
        List of enriched model card dicts.
    """
    now = time.time()
    if not refresh and _model_cache["models"] and (now - _model_cache["fetched_at"]) < _CACHE_TTL_S:
        return _model_cache["models"]

    api_key = config.OLLAMA_CLOUD_API_KEY
    api_base = getattr(config, "OLLAMA_CLOUD_API_BASE", "https://api.ollama.com")
    if not api_base:
        api_base = "https://api.ollama.com"

    headers: dict[str, str] = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        resp = requests.get(f"{api_base}/api/tags", headers=headers, timeout=15)
        resp.raise_for_status()
        raw_models = resp.json().get("models", [])
    except Exception as exc:
        logger.warning("Failed to fetch Ollama Cloud models: %s", exc)
        # Return cached if available, else empty
        if _model_cache["models"]:
            return _model_cache["models"]
        return []

    enriched = [enrich_model_card(m) for m in raw_models]

    _model_cache["models"] = enriched
    _model_cache["fetched_at"] = now
    logger.info("Fetched %d Ollama Cloud models (enriched)", len(enriched))

    return enriched


# ---------------------------------------------------------------------------
# Suggestion engine
# ---------------------------------------------------------------------------


# Per-tier primary models from config (reads env vars / system config).
DEFAULT_PRIMARY_SMALL = config.OLLAMA_CLOUD_MODEL_SMALL    # ollama/gemma3:4b
DEFAULT_PRIMARY_MEDIUM = config.OLLAMA_CLOUD_MODEL_MEDIUM  # ollama/gemma3:12b
DEFAULT_PRIMARY_LARGE = config.OLLAMA_CLOUD_MODEL_LARGE    # ollama/gemma3:27b

# Multimodal models for specific media types (Ollama Cloud).
DEFAULT_MULTIMODAL_MODEL = config.OLLAMA_CLOUD_MODEL_MULTIMODAL  # ollama/qwen3-vl:235b-cloud
DEFAULT_OMNI_MODEL = config.OLLAMA_CLOUD_MODEL_OMNI              # ollama/qwen3.5:cloud

# Data types that need vision (image/PDF) — routed to qwen3-vl.
_VISION_DATA_TYPES = {"image", "image_batch", "pdf", "medical_imaging"}

# Data types that need audio/video — routed to qwen3.5 omni model.
_AV_DATA_TYPES = {"video_url", "video_stream", "audio_url", "audio_stream"}

# Default fallback provider/model (Gemini).
DEFAULT_FALLBACK_MODEL = config.DATA_PIPELINE_AI_FALLBACK_MODEL or "gemini/gemini-3.1-pro-preview"

# Map min_tier to default primary model.
_TIER_PRIMARY: dict[str, str] = {
    "small": DEFAULT_PRIMARY_SMALL,
    "medium": DEFAULT_PRIMARY_MEDIUM,
    "large": DEFAULT_PRIMARY_LARGE,
}


def suggest_model(
    data_type: str,
    available_models: list[dict],
) -> dict[str, str]:
    """Suggest primary + fallback models for a data type.

    Routing:
    - Audio/video → omni model (native audio+video support)
    - Image/PDF   → multimodal vision model
    - Text types  → tier-appropriate model (small/medium/large)
    Fallback is always Gemini.

    Args:
        data_type: One of the keys in DATA_TYPE_REQUIREMENTS.
        available_models: Enriched model cards from fetch_ollama_cloud_models().

    Returns:
        Dict with ``primary``, ``fallback``, and ``reason``.
    """
    if data_type in _AV_DATA_TYPES:
        return {
            "primary": DEFAULT_OMNI_MODEL,
            "fallback": DEFAULT_FALLBACK_MODEL,
            "reason": f"Omni: {DEFAULT_OMNI_MODEL} (native audio/video), fallback: Gemini",
        }

    if data_type in _VISION_DATA_TYPES:
        return {
            "primary": DEFAULT_MULTIMODAL_MODEL,
            "fallback": DEFAULT_FALLBACK_MODEL,
            "reason": f"Vision: {DEFAULT_MULTIMODAL_MODEL} (image/PDF), fallback: Gemini",
        }

    # Tier-based primary selection for text data types.
    reqs = DATA_TYPE_REQUIREMENTS.get(data_type, {})
    min_tier = reqs.get("min_tier", "medium")
    primary = _TIER_PRIMARY.get(min_tier, DEFAULT_PRIMARY_MEDIUM)

    return {
        "primary": primary,
        "fallback": DEFAULT_FALLBACK_MODEL,
        "reason": f"{min_tier.title()}: {primary} (Ollama Cloud), fallback: Gemini",
    }


def get_routing_table(available_models: Optional[list[dict]] = None) -> dict[str, dict[str, str]]:
    """Build a full routing suggestion table for all data types.

    Args:
        available_models: If None, fetches from Ollama Cloud.

    Returns:
        Dict keyed by data_type, each value a suggestion dict.
    """
    if available_models is None:
        available_models = fetch_ollama_cloud_models()

    return {
        dt: suggest_model(dt, available_models)
        for dt in DATA_TYPE_REQUIREMENTS
    }


def get_merged_routing(
    user_overrides: dict[str, dict[str, str]],
    available_models: Optional[list[dict]] = None,
) -> dict[str, dict[str, Any]]:
    """Merge system suggestions with user overrides.

    Args:
        user_overrides: From user's ``smart_routing_overrides`` preferences.
        available_models: If None, fetches from Ollama Cloud.

    Returns:
        Dict keyed by data_type with ``primary``, ``fallback``, ``reason``,
        ``is_override``, and ``suggested_primary``/``suggested_fallback``.
    """
    suggestions = get_routing_table(available_models)
    merged: dict[str, dict[str, Any]] = {}

    for dt, suggestion in suggestions.items():
        override = user_overrides.get(dt, {})
        entry: dict[str, Any] = {
            "suggested_primary": suggestion["primary"],
            "suggested_fallback": suggestion["fallback"],
            "reason": suggestion["reason"],
        }

        if override.get("primary_model"):
            entry["primary"] = override["primary_model"]
            entry["is_override"] = True
        else:
            entry["primary"] = suggestion["primary"]
            entry["is_override"] = False

        if override.get("fallback_model"):
            entry["fallback"] = override["fallback_model"]
        else:
            entry["fallback"] = suggestion["fallback"]

        merged[dt] = entry

    return merged
