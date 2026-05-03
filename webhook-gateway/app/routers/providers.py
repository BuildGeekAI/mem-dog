"""LLM provider status and info endpoints."""

from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter

from .. import config
from ..llm import get_provider_info

router = APIRouter(prefix="/providers", tags=["providers"])

KNOWN_PROVIDERS: dict[str, dict[str, str]] = {
    "gemini": {"name": "Google Gemini", "env_key": "GEMINI_API_KEY", "docs": "https://docs.openclaw.ai/providers/models"},
    "openai": {"name": "OpenAI", "env_key": "OPENAI_API_KEY", "docs": "https://docs.openclaw.ai/providers/openai"},
    "anthropic": {"name": "Anthropic", "env_key": "ANTHROPIC_API_KEY", "docs": "https://docs.openclaw.ai/providers/anthropic"},
    "openrouter": {"name": "OpenRouter", "env_key": "OPENROUTER_API_KEY", "docs": "https://docs.openclaw.ai/providers/openrouter"},
    "mistral": {"name": "Mistral", "env_key": "MISTRAL_API_KEY", "docs": "https://docs.openclaw.ai/providers/mistral"},
    "together_ai": {"name": "Together AI", "env_key": "TOGETHERAI_API_KEY", "docs": "https://docs.openclaw.ai/providers/together"},
    "bedrock": {"name": "Amazon Bedrock", "env_key": "AWS_ACCESS_KEY_ID", "docs": "https://docs.openclaw.ai/providers/bedrock"},
    "ollama": {"name": "Ollama (local)", "env_key": "", "docs": "https://docs.openclaw.ai/providers/ollama"},
    "vllm": {"name": "vLLM (local)", "env_key": "", "docs": "https://docs.openclaw.ai/providers/vllm"},
    "cloudflare": {"name": "Cloudflare AI Gateway", "env_key": "CLOUDFLARE_API_KEY", "docs": "https://docs.openclaw.ai/providers/cloudflare-ai-gateway"},
    "nvidia_nim": {"name": "NVIDIA NIM", "env_key": "NVIDIA_API_KEY", "docs": "https://docs.openclaw.ai/providers/nvidia"},
    "huggingface": {"name": "Hugging Face", "env_key": "HUGGINGFACE_API_KEY", "docs": "https://docs.openclaw.ai/providers/huggingface"},
    "litellm": {"name": "LiteLLM Proxy", "env_key": "", "docs": "https://docs.openclaw.ai/providers/litellm"},
    "vercel": {"name": "Vercel AI Gateway", "env_key": "", "docs": "https://docs.openclaw.ai/providers/vercel-ai-gateway"},
    "qianfan": {"name": "Qianfan", "env_key": "QIANFAN_ACCESS_KEY", "docs": "https://docs.openclaw.ai/providers/qianfan"},
    "moonshot": {"name": "Moonshot AI", "env_key": "MOONSHOT_API_KEY", "docs": "https://docs.openclaw.ai/providers/moonshot"},
    "glm": {"name": "GLM Models", "env_key": "", "docs": "https://docs.openclaw.ai/providers/glm"},
    "minimax": {"name": "MiniMax", "env_key": "", "docs": "https://docs.openclaw.ai/providers/minimax"},
    "venice": {"name": "Venice AI", "env_key": "", "docs": "https://docs.openclaw.ai/providers/venice"},
    "deepgram": {"name": "Deepgram (transcription)", "env_key": "DEEPGRAM_API_KEY", "docs": "https://docs.openclaw.ai/providers/deepgram"},
}


@router.get("")
async def list_providers() -> dict[str, Any]:
    """Return the active provider, model, and the catalog of known providers."""
    active = get_provider_info()
    catalog = []
    for key, meta in KNOWN_PROVIDERS.items():
        env_key = meta["env_key"]
        has_key = bool(os.getenv(env_key)) if env_key else None
        catalog.append({
            "id": key,
            "name": meta["name"],
            "configured": has_key if has_key is not None else (bool(config.LLM_API_BASE) if key in ("ollama", "vllm", "litellm") else False),
            "active": key == config.LLM_PROVIDER,
            "docs": meta["docs"],
        })
    return {"active": active, "providers": catalog}


@router.get("/active")
async def active_provider() -> dict[str, Any]:
    """Return details about the currently active LLM provider."""
    return get_provider_info()
