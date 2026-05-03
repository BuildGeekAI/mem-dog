"""Multi-provider LLM client for message classification and summarisation.

Supports 20+ providers via litellm (OpenAI, Anthropic, Mistral, Bedrock,
Ollama, vLLM, OpenRouter, Together AI, etc.) plus the native Google GenAI
SDK for Gemini.

Provider selection is controlled by ``LLM_PROVIDER`` env var.  When set to
``"gemini"`` (the default), the native ``google-genai`` SDK is used.  Any
other value routes through litellm's unified ``acompletion`` interface.

Both ``classify_message`` and ``summarize_context`` gracefully degrade
(return empty/neutral results) when the provider is not configured or the
call fails, so the gateway never blocks on LLM errors.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from . import config

_log = logging.getLogger("openclaw_gateway.llm")

_CLASSIFY_SYSTEM = (
    "You are a message classifier. Given the text, return ONLY a JSON object "
    "with keys: intent (one of: informational, action_required, spam, "
    "meeting_summary, recording, unknown), category (short label), "
    "confidence (float 0-1). No markdown, no extra text."
)

_SUMMARIZE_SYSTEM = (
    "You are a concise summariser. Given the text, return a 1-3 sentence "
    "summary capturing the key points. No markdown, no extra text."
)

_FALLBACK_CLASSIFY: dict[str, Any] = {
    "intent": "unknown",
    "category": "unclassified",
    "confidence": 0.0,
}

# ---------------------------------------------------------------------------
# Native Gemini client (backward-compatible path)
# ---------------------------------------------------------------------------


def _get_gemini_client():
    """Lazy-import and instantiate the native Gemini client."""
    try:
        from google import genai  # type: ignore[import-untyped]
        return genai.Client(api_key=config.GEMINI_API_KEY)
    except Exception as exc:
        _log.warning("Failed to create Gemini client: %s", exc)
        return None


async def _gemini_complete(system: str, text: str, *, temperature: float, max_tokens: int) -> str:
    """Call the native Gemini SDK and return the response text."""
    client = _get_gemini_client()
    if client is None:
        return ""
    response = client.models.generate_content(
        model=config.GEMINI_MODEL,
        contents=text,
        config={
            "system_instruction": system,
            "temperature": temperature,
            "max_output_tokens": max_tokens,
        },
    )
    return response.text.strip()


# ---------------------------------------------------------------------------
# litellm path (all other providers)
# ---------------------------------------------------------------------------


async def _litellm_complete(system: str, text: str, *, temperature: float, max_tokens: int) -> str:
    """Call litellm ``acompletion`` and return the response text."""
    import litellm  # type: ignore[import-untyped]

    litellm.drop_params = True

    kwargs: dict[str, Any] = {
        "model": config.get_effective_model(),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": text},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if config.LLM_API_KEY:
        kwargs["api_key"] = config.LLM_API_KEY
    if config.LLM_API_BASE:
        kwargs["api_base"] = config.LLM_API_BASE

    response = await litellm.acompletion(**kwargs)
    return response.choices[0].message.content.strip()


# ---------------------------------------------------------------------------
# Unified dispatch
# ---------------------------------------------------------------------------


async def _complete(system: str, text: str, *, temperature: float = 0.1, max_tokens: int = 256) -> str:
    """Route to the appropriate LLM backend and return raw response text."""
    if config.LLM_PROVIDER == "gemini":
        return await _gemini_complete(system, text, temperature=temperature, max_tokens=max_tokens)
    return await _litellm_complete(system, text, temperature=temperature, max_tokens=max_tokens)


def _strip_markdown(raw: str) -> str:
    """Remove markdown code fences if present."""
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    return raw


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def classify_message(text: str) -> dict[str, Any]:
    """Classify *text* via the configured LLM provider.

    Returns ``{"intent": ..., "category": ..., "confidence": ...}``
    or a neutral fallback on error.
    """
    if not config.has_llm_configured() or not text:
        return dict(_FALLBACK_CLASSIFY)

    try:
        raw = await _complete(_CLASSIFY_SYSTEM, text[:4000], temperature=0.1, max_tokens=256)
        return json.loads(_strip_markdown(raw))
    except Exception as exc:
        _log.warning("classify_message failed (%s): %s", config.LLM_PROVIDER, exc)
        return dict(_FALLBACK_CLASSIFY)


async def summarize_context(text: str) -> str:
    """Summarise *text* via the configured LLM provider.

    Returns a short summary string, or an empty string on error.
    """
    if not config.has_llm_configured() or not text:
        return ""

    try:
        return await _complete(_SUMMARIZE_SYSTEM, text[:8000], temperature=0.3, max_tokens=512)
    except Exception as exc:
        _log.warning("summarize_context failed (%s): %s", config.LLM_PROVIDER, exc)
        return ""


def get_provider_info() -> dict[str, Any]:
    """Return metadata about the active LLM provider for diagnostics."""
    return {
        "provider": config.LLM_PROVIDER,
        "model": config.get_effective_model(),
        "configured": config.has_llm_configured(),
        "api_base": config.LLM_API_BASE or None,
    }
