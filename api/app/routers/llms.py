"""LLMs router for model categories.

Provides CRUD endpoints for managing LLM configurations (Gemini, Anthropic, OpenAI, etc.).
API keys are encrypted at rest and never returned in responses.
All operations are scoped to the authenticated user.

For provider=custom (Local): also provides Ollama model control (list, load, unload).
"""

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import httpx
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from app import config, crypto
from app.gcp_auth import get_identity_token_for_url
from app.models import (
    PublicLlmCreate,
    PublicLlmUpdate,
    PublicLlmResponse,
)
from app.storage import get_storage

logger = logging.getLogger("mem_dog.llms")

router = APIRouter(prefix="/api/v1/models/public-llms", tags=["Model Categories - LLMs"])


def _load_ollama_open_models() -> list[dict[str, str]]:
    """Load Ollama open models from ollama-capacity-catalog.json for Local provider dropdown."""
    path = Path(__file__).resolve().parent.parent / "data" / "ollama-capacity-catalog.json"
    try:
        data = json.loads(path.read_text())
        models = data.get("models", {})
        if not isinstance(models, dict):
            return []
        result = []
        for model_id in sorted(models.keys()):
            # Skip embedding-only models
            if "embed" in model_id.lower():
                continue
            # Format display name: gemma3:1b -> Gemma 3 1B, llama3.2:3b -> Llama 3.2 3B
            parts = model_id.replace("-", " ").split(":")
            if len(parts) == 2:
                base = re.sub(r"(?<=[a-zA-Z])(?=\d)", " ", parts[0].strip()).title()
                size = parts[1].strip()
                if size and size[-1].lower() == "b":
                    size = size[:-1] + "B"
                name = f"{base} {size}"
            else:
                name = model_id.replace("-", " ").replace("_", " ").title()
            result.append({"id": model_id, "name": name})
        return result
    except Exception as exc:
        logger.warning("Could not load Ollama catalog for Local models: %s", exc)
        return []


# LiteLLM-supported completion models per provider (used for UI dropdowns).
# Exhaustive lists; see https://docs.litellm.ai/docs/providers
PUBLIC_LLM_PROVIDER_MODELS: dict[str, list[dict[str, str]]] = {
    "openai": [
        {"id": "gpt-4o", "name": "GPT-4o"},
        {"id": "gpt-4o-mini", "name": "GPT-4o mini"},
        {"id": "gpt-4o-audio-preview", "name": "GPT-4o Audio Preview"},
        {"id": "gpt-4o-audio", "name": "GPT-4o Audio"},
        {"id": "gpt-4-turbo", "name": "GPT-4 Turbo"},
        {"id": "gpt-4-turbo-preview", "name": "GPT-4 Turbo Preview"},
        {"id": "gpt-4-turbo-2024-04-09", "name": "GPT-4 Turbo (2024-04-09)"},
        {"id": "gpt-4", "name": "GPT-4"},
        {"id": "gpt-4-32k", "name": "GPT-4 32K"},
        {"id": "gpt-4-1106-preview", "name": "GPT-4 (2023-11-06)"},
        {"id": "gpt-4-0613", "name": "GPT-4 (2023-06-13)"},
        {"id": "gpt-3.5-turbo", "name": "GPT-3.5 Turbo"},
        {"id": "gpt-3.5-turbo-16k", "name": "GPT-3.5 Turbo 16K"},
        {"id": "gpt-3.5-turbo-1106", "name": "GPT-3.5 Turbo (2023-11-06)"},
        {"id": "gpt-3.5-turbo-0613", "name": "GPT-3.5 Turbo (2023-06-13)"},
        {"id": "o1", "name": "O1"},
        {"id": "o1-mini", "name": "O1 Mini"},
        {"id": "o1-preview", "name": "O1 Preview"},
        {"id": "o3-mini", "name": "O3 Mini"},
    ],
    "anthropic": [
        {"id": "claude-opus-4-6-20250605", "name": "Claude Opus 4.6 (2025-06-05)"},
        {"id": "claude-sonnet-4-6-20250514", "name": "Claude Sonnet 4.6 (2025-05-14)"},
        {"id": "claude-haiku-4-5-20251001", "name": "Claude Haiku 4.5"},
        {"id": "claude-3-5-sonnet-20241022", "name": "Claude 3.5 Sonnet"},
        {"id": "claude-3-5-haiku-20241022", "name": "Claude 3.5 Haiku"},
        {"id": "claude-3-opus-20240229", "name": "Claude 3 Opus"},
        {"id": "claude-3-sonnet-20240229", "name": "Claude 3 Sonnet"},
        {"id": "claude-3-haiku-20240307", "name": "Claude 3 Haiku"},
        {"id": "claude-2.1", "name": "Claude 2.1"},
        {"id": "claude-2.0", "name": "Claude 2.0"},
        {"id": "claude-instant-1.2", "name": "Claude Instant 1.2"},
        {"id": "claude-instant-1.1", "name": "Claude Instant 1.1"},
    ],
    "gemini": [
        {"id": "gemini-3.1-pro-preview", "name": "Gemini 3.1 Pro Preview"},
        {"id": "gemini-3.1-pro-preview", "name": "Gemini 3.1 Pro Preview"},
        {"id": "gemini-3.1-pro-preview", "name": "Gemini 3.1 Pro Preview"},
        {"id": "gemini-3.1-flash-preview", "name": "Gemini 3.1 Flash Preview"},
        {"id": "gemini-3.1-flash-lite-preview", "name": "Gemini 3.1 Flash Lite Preview"},
        {"id": "gemini-2.5-pro", "name": "Gemini 2.5 Pro"},
        {"id": "gemini-2.5-flash", "name": "Gemini 2.5 Flash"},
        {"id": "gemini-2.5-flash-lite", "name": "Gemini 2.5 Flash Lite"},
        {"id": "gemini-1.5-pro", "name": "Gemini 1.5 Pro"},
        {"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash"},
    ],
    "xai": [
        {"id": "grok-4-1-fast-reasoning", "name": "Grok 4.1 Fast (Reasoning)"},
        {"id": "grok-4-1-fast-non-reasoning", "name": "Grok 4.1 Fast (Non-Reasoning)"},
        {"id": "grok-4", "name": "Grok 4"},
        {"id": "grok-4-0709", "name": "Grok 4 (0709)"},
        {"id": "grok-4-fast-reasoning", "name": "Grok 4 Fast (Reasoning)"},
        {"id": "grok-4-fast-non-reasoning", "name": "Grok 4 Fast (Non-Reasoning)"},
        {"id": "grok-3", "name": "Grok 3"},
        {"id": "grok-3-mini", "name": "Grok 3 Mini"},
        {"id": "grok-3-fast-beta", "name": "Grok 3 Fast Beta"},
        {"id": "grok-code-fast", "name": "Grok Code Fast"},
        {"id": "grok-2", "name": "Grok 2"},
        {"id": "grok-2-vision-latest", "name": "Grok 2 Vision"},
    ],
    "mistral": [
        {"id": "mistral-small-latest", "name": "Mistral Small Latest"},
        {"id": "mistral-medium-latest", "name": "Mistral Medium Latest"},
        {"id": "mistral-large-2407", "name": "Mistral Large 2407"},
        {"id": "mistral-large-latest", "name": "Mistral Large Latest"},
        {"id": "magistral-small-2506", "name": "Magistral Small 2506"},
        {"id": "magistral-medium-2506", "name": "Magistral Medium 2506"},
        {"id": "open-mistral-7b", "name": "Open Mistral 7B"},
        {"id": "open-mixtral-8x7b", "name": "Open Mixtral 8x7B"},
        {"id": "open-mixtral-8x22b", "name": "Open Mixtral 8x22B"},
        {"id": "codestral-latest", "name": "Codestral Latest"},
        {"id": "open-mistral-nemo", "name": "Open Mistral NeMo"},
        {"id": "open-mistral-nemo-2407", "name": "Open Mistral NeMo 2407"},
        {"id": "open-codestral-mamba", "name": "Open Codestral Mamba"},
        {"id": "codestral-mamba-latest", "name": "Codestral Mamba Latest"},
    ],
    "cohere_chat": [
        {"id": "command-a-03-2025", "name": "Command A 03-2025"},
        {"id": "command-r-plus-08-2024", "name": "Command R+ 08-2024"},
        {"id": "command-r-08-2024", "name": "Command R 08-2024"},
        {"id": "command-r-plus", "name": "Command R+"},
        {"id": "command-r", "name": "Command R"},
        {"id": "command-light", "name": "Command Light"},
        {"id": "command-nightly", "name": "Command Nightly"},
    ],
    "groq": [
        {"id": "llama-3.3-70b-versatile", "name": "Llama 3.3 70B Versatile"},
        {"id": "llama-3.1-8b-instant", "name": "Llama 3.1 8B Instant"},
        {"id": "llama-3.1-70b-versatile", "name": "Llama 3.1 70B Versatile"},
        {"id": "llama-3.1-405b-reasoning", "name": "Llama 3.1 405B Reasoning"},
        {"id": "llama3-8b-8192", "name": "Llama 3 8B 8192"},
        {"id": "llama3-70b-8192", "name": "Llama 3 70B 8192"},
        {"id": "meta-llama/llama-4-scout-17b-16e-instruct", "name": "Llama 4 Scout 17B"},
        {"id": "meta-llama/llama-4-maverick-17b-128e-instruct", "name": "Llama 4 Maverick 17B"},
        {"id": "meta-llama/llama-guard-4-12b", "name": "Llama Guard 4 12B"},
        {"id": "qwen/qwen3-32b", "name": "Qwen3 32B"},
        {"id": "moonshotai/kimi-k2-instruct-0905", "name": "Kimi K2 Instruct"},
        {"id": "openai/gpt-oss-120b", "name": "GPT-OSS 120B"},
        {"id": "openai/gpt-oss-20b", "name": "GPT-OSS 20B"},
    ],
    "deepseek": [
        {"id": "deepseek-chat", "name": "DeepSeek Chat"},
        {"id": "deepseek-coder", "name": "DeepSeek Coder"},
        {"id": "deepseek-reasoner", "name": "DeepSeek Reasoner"},
    ],
    "togetherai": [
        {"id": "meta-llama/Meta-Llama-3.1-405B-Instruct-Turbo", "name": "Llama 3.1 405B Instruct Turbo"},
        {"id": "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo", "name": "Llama 3.1 70B Instruct Turbo"},
        {"id": "meta-llama/Meta-Llama-3-70B-Instruct-v1", "name": "Llama 3 70B Instruct"},
        {"id": "mistralai/Mixtral-8x22B-Instruct-v0.1", "name": "Mixtral 8x22B Instruct"},
        {"id": "mistralai/Mixtral-8x7B-Instruct-v0.1", "name": "Mixtral 8x7B Instruct"},
        {"id": "Qwen/Qwen2-72B-Instruct", "name": "Qwen2 72B Instruct"},
        {"id": "deepseek-ai/DeepSeek-V3", "name": "DeepSeek V3"},
        {"id": "deepseek-ai/DeepSeek-V3-0324", "name": "DeepSeek V3 0324"},
    ],
    # Ollama Cloud: https://ollama.com with API key; uses LiteLLM ollama provider + api_base
    "ollama_cloud": [
        {"id": "cogito-2.1:671b", "name": "Cogito 2.1 671B"},
        {"id": "deepseek-v3.1:671b", "name": "DeepSeek V3.1 671B"},
        {"id": "deepseek-v3.2", "name": "DeepSeek V3.2"},
        {"id": "devstral-2:123b", "name": "Devstral 2 123B"},
        {"id": "devstral-small-2:24b", "name": "Devstral Small 2 24B"},
        {"id": "gemini-3.1-pro-preview", "name": "Gemini 3 Flash Preview"},
        {"id": "gemini-3-pro-preview", "name": "Gemini 3 Pro Preview"},
        {"id": "gemma3:12b", "name": "Gemma 3 12B"},
        {"id": "gemma3:27b", "name": "Gemma 3 27B"},
        {"id": "gemma3:4b", "name": "Gemma 3 4B"},
        {"id": "glm-4.6", "name": "GLM 4.6"},
        {"id": "glm-4.7", "name": "GLM 4.7"},
        {"id": "glm-5", "name": "GLM 5"},
        {"id": "gpt-oss:120b", "name": "GPT-OSS 120B"},
        {"id": "gpt-oss:20b", "name": "GPT-OSS 20B"},
        {"id": "kimi-k2-thinking", "name": "Kimi K2 Thinking"},
        {"id": "kimi-k2:1t", "name": "Kimi K2 1T"},
        {"id": "kimi-k2.5", "name": "Kimi K2.5"},
        {"id": "minimax-m2", "name": "MiniMax M2"},
        {"id": "minimax-m2.1", "name": "MiniMax M2.1"},
        {"id": "minimax-m2.5", "name": "MiniMax M2.5"},
        {"id": "ministral-3:14b", "name": "Ministral 3 14B"},
        {"id": "ministral-3:3b", "name": "Ministral 3 3B"},
        {"id": "ministral-3:8b", "name": "Ministral 3 8B"},
        {"id": "mistral-large-3:675b", "name": "Mistral Large 3 675B"},
        {"id": "nemotron-3-nano:30b", "name": "Nemotron 3 Nano 30B"},
        {"id": "qwen3-coder-next", "name": "Qwen3 Coder Next"},
        {"id": "qwen3-coder:480b", "name": "Qwen3 Coder 480B"},
        {"id": "qwen3-next:80b", "name": "Qwen3 Next 80B"},
        {"id": "qwen3-vl:235b", "name": "Qwen3 VL 235B"},
        {"id": "qwen3-vl:235b-instruct", "name": "Qwen3 VL 235B Instruct"},
        {"id": "qwen3.5:397b", "name": "Qwen 3.5 397B"},
        {"id": "rnj-1:8b", "name": "RNJ 1 8B"},
    ],
    # OpenRouter: single API for 100+ models; model_id = upstream e.g. openai/gpt-4o
    "openrouter": [
        {"id": "openai/gpt-4o", "name": "OpenAI GPT-4o"},
        {"id": "openai/gpt-4o-mini", "name": "OpenAI GPT-4o mini"},
        {"id": "openai/gpt-4-turbo", "name": "OpenAI GPT-4 Turbo"},
        {"id": "openai/gpt-4", "name": "OpenAI GPT-4"},
        {"id": "openai/gpt-3.5-turbo", "name": "OpenAI GPT-3.5 Turbo"},
        {"id": "anthropic/claude-3.5-sonnet", "name": "Anthropic Claude 3.5 Sonnet"},
        {"id": "anthropic/claude-3-opus", "name": "Anthropic Claude 3 Opus"},
        {"id": "anthropic/claude-3-sonnet", "name": "Anthropic Claude 3 Sonnet"},
        {"id": "anthropic/claude-3-haiku", "name": "Anthropic Claude 3 Haiku"},
        {"id": "anthropic/claude-2", "name": "Anthropic Claude 2"},
        {"id": "google/gemini-2.5-flash", "name": "Google Gemini 2.5 Flash"},
        {"id": "google/gemini-2.5-pro", "name": "Google Gemini 2.5 Pro"},
        {"id": "google/gemini-1.5-pro", "name": "Google Gemini 1.5 Pro"},
        {"id": "google/gemini-1.5-flash", "name": "Google Gemini 1.5 Flash"},
        {"id": "meta-llama/llama-3.1-405b-instruct", "name": "Meta Llama 3.1 405B Instruct"},
        {"id": "meta-llama/llama-3.1-70b-instruct", "name": "Meta Llama 3.1 70B Instruct"},
        {"id": "meta-llama/llama-3-70b-instruct", "name": "Meta Llama 3 70B Instruct"},
        {"id": "mistralai/mistral-large", "name": "Mistral Large"},
        {"id": "mistralai/mixtral-8x7b-instruct", "name": "Mistral Mixtral 8x7B Instruct"},
        {"id": "deepseek/deepseek-chat-v3", "name": "DeepSeek Chat V3"},
        {"id": "deepseek/deepseek-coder", "name": "DeepSeek Coder"},
        {"id": "qwen/qwen-2.5-72b-instruct", "name": "Qwen 2.5 72B Instruct"},
        {"id": "cohere/command-r-plus", "name": "Cohere Command R+"},
        {"id": "perplexity/llama-3.1-sonar-large-128k-online", "name": "Perplexity Sonar Large Online"},
        {"id": "microsoft/phi-3-medium", "name": "Microsoft Phi 3 Medium"},
    ],
    # OpenClaw-aligned providers (see https://docs.openclaw.ai/concepts/model-providers)
    "moonshot": [
        {"id": "kimi-k2.5", "name": "Kimi K2.5"},
        {"id": "kimi-k2-thinking", "name": "Kimi K2 Thinking"},
        {"id": "kimi-k2-thinking-turbo", "name": "Kimi K2 Thinking Turbo"},
        {"id": "kimi-k2-0905-preview", "name": "Kimi K2 0905 Preview"},
        {"id": "kimi-k2-turbo-preview", "name": "Kimi K2 Turbo Preview"},
        {"id": "moonshot-v1-8k", "name": "Moonshot v1 8K"},
        {"id": "moonshot-v1-32k", "name": "Moonshot v1 32K"},
        {"id": "moonshot-v1-128k", "name": "Moonshot v1 128K"},
    ],
    "cerebras": [
        {"id": "llama3-70b-instruct", "name": "Llama 3 70B Instruct"},
        {"id": "llama3-8b-instruct", "name": "Llama 3 8B Instruct"},
        {"id": "llama-3.3-70b-instruct", "name": "Llama 3.3 70B Instruct"},
        {"id": "llama-3.3-8b-instruct", "name": "Llama 3.3 8B Instruct"},
    ],
    "zai": [
        {"id": "glm-4.7", "name": "GLM 4.7"},
        {"id": "glm-4.6", "name": "GLM 4.6"},
        {"id": "glm-4.5", "name": "GLM 4.5"},
        {"id": "glm-4.5v", "name": "GLM 4.5V (Vision)"},
        {"id": "glm-4.5-flash", "name": "GLM 4.5 Flash (Free)"},
        {"id": "glm-4.5-air", "name": "GLM 4.5 Air"},
    ],
    "huggingface": [
        {"id": "together/deepseek-ai/DeepSeek-R1", "name": "DeepSeek R1 (Together)"},
        {"id": "together/deepseek-ai/DeepSeek-V3", "name": "DeepSeek V3 (Together)"},
        {"id": "sambanova/Qwen/Qwen2.5-72B-Instruct", "name": "Qwen 2.5 72B (SambaNova)"},
        {"id": "meta-llama/Llama-3.3-70B-Instruct", "name": "Llama 3.3 70B (HF Inference)"},
    ],
    "vercel_ai_gateway": [
        {"id": "openai/gpt-4o", "name": "OpenAI GPT-4o"},
        {"id": "openai/gpt-4o-mini", "name": "OpenAI GPT-4o mini"},
        {"id": "anthropic/claude-3.5-sonnet", "name": "Anthropic Claude 3.5 Sonnet"},
        {"id": "anthropic/claude-sonnet-4.6", "name": "Anthropic Claude Sonnet 4.6"},
        {"id": "google/gemini-2.5-flash", "name": "Google Gemini 2.5 Flash"},
    ],
    "minimax": [
        {"id": "MiniMax-M2.1", "name": "MiniMax M2.1"},
        {"id": "MiniMax-M2.1-lightning", "name": "MiniMax M2.1 Lightning"},
        {"id": "MiniMax-M2", "name": "MiniMax M2"},
    ],
    "custom": _load_ollama_open_models(),  # Local Ollama: open models from ollama-capacity-catalog
}

# Provider id -> display label (dynamic; add new providers here)
# Aligned with OpenClaw model providers: https://docs.openclaw.ai/concepts/model-providers
PROVIDER_LABELS: dict[str, str] = {
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "gemini": "Google Gemini",
    "xai": "xAI (Grok)",
    "mistral": "Mistral AI",
    "cohere_chat": "Cohere",
    "groq": "Groq",
    "deepseek": "DeepSeek",
    "togetherai": "Together AI",
    "ollama_cloud": "Ollama Cloud",
    "openrouter": "OpenRouter",
    "moonshot": "Moonshot (Kimi)",
    "cerebras": "Cerebras",
    "zai": "Z.AI (GLM)",
    "huggingface": "Hugging Face",
    "vercel_ai_gateway": "Vercel AI Gateway",
    "minimax": "MiniMax",
    "custom": "Local",
}


# Temporary: Mock user auth until full auth is implemented
def get_current_user() -> str:
    """Return the authenticated user ID."""
    # TODO: Replace with actual auth middleware
    return config.DEFAULT_USER_ID


class PublicLlmListResponse(BaseModel):
    public_llms: List[PublicLlmResponse]


class ProviderModel(BaseModel):
    """A model option for a given LLM provider."""
    id: str
    name: str


class ProviderModelsResponse(BaseModel):
    """List of models available for a provider (for UI dropdowns)."""
    provider: str
    models: List[ProviderModel]


class ProviderInfo(BaseModel):
    id: str
    label: str


class ProvidersListResponse(BaseModel):
    """List of LLM providers (for dynamic UI)."""
    providers: List[ProviderInfo]


@router.get("/providers", response_model=ProvidersListResponse)
async def list_providers():
    """List all LLM providers. UI uses this to build the provider dropdown dynamically."""
    providers = [
        ProviderInfo(id=pid, label=PROVIDER_LABELS.get(pid, pid.replace("_", " ").title()))
        for pid in PUBLIC_LLM_PROVIDER_MODELS
    ]
    return ProvidersListResponse(providers=providers)


@router.get("/providers/{provider}/models", response_model=ProviderModelsResponse)
async def list_provider_models(provider: str):
    """List all completion models for an LLM provider.

    Supported providers: openai, anthropic, gemini, xai (Grok), mistral, cohere_chat,
    groq, deepseek, togetherai, ollama_cloud, openrouter, custom. For ``custom`` (Local),
    returns Ollama open models from ollama-capacity-catalog.json.
    """
    if provider not in PUBLIC_LLM_PROVIDER_MODELS:
        raise HTTPException(404, f"Unknown provider: {provider}")
    models = [
        ProviderModel(id=m["id"], name=m["name"])
        for m in PUBLIC_LLM_PROVIDER_MODELS[provider]
    ]
    return ProviderModelsResponse(provider=provider, models=models)


@router.post("", response_model=PublicLlmResponse, status_code=201)
async def create_public_llm(req: PublicLlmCreate, current_user: str = Depends(get_current_user)):
    """Create a new LLM configuration.
    
    The API key is encrypted before storage and never returned in responses.
    """
    try:
        storage = get_storage()
        encrypted_key = None
        if req.api_key and req.api_key.strip():
            if not crypto.is_encryption_available():
                raise HTTPException(503, "Encryption not configured (MASTER_ENCRYPTION_KEY not set)")
            encrypted_key = crypto.encrypt_api_key(req.api_key)
        model_id = (req.model_id or "").strip()
        result = storage.create_public_llm(
            provider=req.provider,
            model_id=model_id,
            display_name=req.display_name,
            api_key_encrypted=encrypted_key,
            user_id=current_user,
            api_base_url=req.api_base_url,
            max_tokens_default=req.max_tokens_default,
            temperature_default=req.temperature_default,
        )
        
        # Remove internal fields for response
        response = {k: v for k, v in result.items() if k not in ("user_id", "deleted_at")}
        return PublicLlmResponse(**response)
    
    except ValueError as e:
        # Duplicate entry
        raise HTTPException(409, str(e))
    except RuntimeError as e:
        # Encryption error
        raise HTTPException(503, str(e))
    except Exception as e:
        logger.error(f"Failed to create LLM: {e}")
        raise HTTPException(500, "Failed to create LLM")


@router.get("", response_model=PublicLlmListResponse)
async def list_public_llms(current_user: str = Depends(get_current_user)):
    """List all LLM configurations for the authenticated user.
    
    API keys are never returned; only has_api_key boolean is included.
    """
    try:
        storage = get_storage()
        results = storage.list_public_llms(user_id=current_user, include_deleted=False)
        
        # Remove internal fields
        llms = [
            PublicLlmResponse(**{k: v for k, v in r.items() if k not in ("user_id", "deleted_at")})
            for r in results
        ]
        
        return PublicLlmListResponse(public_llms=llms)
    
    except Exception as e:
        logger.error(f"Failed to list LLMs: {e}")
        raise HTTPException(500, "Failed to list LLMs")


@router.get("/{llm_id}", response_model=PublicLlmResponse)
async def get_public_llm(llm_id: str, current_user: str = Depends(get_current_user)):
    """Get a single LLM configuration by ID.
    
    API key is never returned; only has_api_key boolean is included.
    """
    try:
        storage = get_storage()
        result = storage.get_public_llm(llm_id=llm_id, user_id=current_user, include_key=False)
        
        if not result:
            raise HTTPException(404, "LLM not found")
        
        # Remove internal fields
        response = {k: v for k, v in result.items() if k not in ("user_id", "deleted_at")}
        return PublicLlmResponse(**response)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get LLM: {e}")
        raise HTTPException(500, "Failed to get LLM")


@router.patch("/{llm_id}", response_model=PublicLlmResponse)
async def update_public_llm(
    llm_id: str,
    req: PublicLlmUpdate,
    current_user: str = Depends(get_current_user)
):
    """Update an LLM configuration.
    
    If api_key is provided, it will be encrypted and replace the existing key.
    """
    try:
        storage = get_storage()
        encrypted_key = None
        if req.api_key:
            if not crypto.is_encryption_available():
                raise HTTPException(503, "Encryption not configured (MASTER_ENCRYPTION_KEY not set)")
            encrypted_key = crypto.encrypt_api_key(req.api_key)
        
        result = storage.update_public_llm(
            llm_id=llm_id,
            user_id=current_user,
            provider=req.provider,
            model_id=req.model_id,
            display_name=req.display_name,
            api_key_encrypted=encrypted_key,
            api_base_url=req.api_base_url,
            max_tokens_default=req.max_tokens_default,
            temperature_default=req.temperature_default,
        )
        
        if not result:
            raise HTTPException(404, "LLM not found")
        
        # Remove internal fields
        response = {k: v for k, v in result.items() if k not in ("user_id", "deleted_at")}
        return PublicLlmResponse(**response)
    
    except HTTPException:
        raise
    except RuntimeError as e:
        # Encryption error
        raise HTTPException(503, str(e))
    except Exception as e:
        logger.error(f"Failed to update LLM: {e}")
        raise HTTPException(500, "Failed to update LLM")


@router.delete("/{llm_id}", status_code=204)
async def delete_public_llm(llm_id: str, current_user: str = Depends(get_current_user)):
    """Delete (soft delete) an LLM configuration."""
    try:
        storage = get_storage()
        deleted = storage.delete_public_llm(llm_id=llm_id, user_id=current_user)
        
        if not deleted:
            raise HTTPException(404, "LLM not found")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete LLM: {e}")
        raise HTTPException(500, "Failed to delete LLM")


# ---------------------------------------------------------------------------
# Local LLM (provider=custom) Ollama model control
# ---------------------------------------------------------------------------

@dataclass
class _LlmPullTask:
    status: str
    stage: str = ""
    percent: float = 0
    error: Optional[str] = None


_llm_pull_tasks: dict[tuple[str, str], _LlmPullTask] = {}
_llm_pull_tasks_lock = asyncio.Lock()


def _ollama_auth_headers(base_url: str) -> dict[str, str]:
    token = get_identity_token_for_url(base_url)
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


async def _ollama_request(base_url: str, method: str, path: str, **kwargs) -> dict:
    url = f"{base_url.rstrip('/')}{path}"
    headers = _ollama_auth_headers(base_url)
    async with httpx.AsyncClient(timeout=300) as client:
        if method == "GET":
            resp = await client.get(url, headers=headers, **kwargs)
        elif method == "POST":
            resp = await client.post(url, headers=headers, **kwargs)
        else:
            raise ValueError(f"Unsupported method {method}")
    resp.raise_for_status()
    return resp.json() if resp.content else {}


def _resolve_local_llm(llm_id: str, current_user: str) -> tuple[dict, str]:
    """Return (llm_record, base_url). Raises HTTPException if not found or not Local."""
    storage = get_storage()
    llm = storage.get_public_llm(llm_id=llm_id, user_id=current_user, include_key=False)
    if not llm:
        raise HTTPException(404, "LLM not found")
    if llm.get("provider") != "custom":
        raise HTTPException(400, "Ollama model control is only for Local (provider=custom) LLMs")
    base_url = (llm.get("api_base_url") or "").strip()
    if not base_url:
        raise HTTPException(400, "Local LLM has no api_base_url")
    return llm, base_url


@router.get("/{llm_id}/ollama/models")
async def list_local_llm_models(llm_id: str, current_user: str = Depends(get_current_user)):
    """List models on disk for a Local LLM (Ollama /api/tags)."""
    _, base_url = _resolve_local_llm(llm_id, current_user)
    data = await _ollama_request(base_url, "GET", "/api/tags")
    return data


@router.get("/{llm_id}/ollama/models/loaded")
async def list_local_llm_loaded(llm_id: str, current_user: str = Depends(get_current_user)):
    """List models currently in memory for a Local LLM (Ollama /api/ps)."""
    _, base_url = _resolve_local_llm(llm_id, current_user)
    data = await _ollama_request(base_url, "GET", "/api/ps")
    return data


@router.post("/{llm_id}/ollama/models/{model_name:path}/pull")
async def pull_local_llm_model(llm_id: str, model_name: str, current_user: str = Depends(get_current_user)):
    """Start async pull for a Local LLM. Returns 202."""
    _, base_url = _resolve_local_llm(llm_id, current_user)
    key = (llm_id, model_name)
    async with _llm_pull_tasks_lock:
        if key in _llm_pull_tasks and _llm_pull_tasks[key].status == "pulling":
            raise HTTPException(409, "Pull already in progress for this model")
        _llm_pull_tasks[key] = _LlmPullTask(status="pulling", stage="starting")

    async def _run():
        nonlocal key
        url = f"{base_url.rstrip('/')}/api/pull"
        headers = _ollama_auth_headers(base_url)
        try:
            async with httpx.AsyncClient(timeout=600) as client:
                async with client.stream("POST", url, json={"name": model_name}, headers=headers) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            status = data.get("status", "")
                            completed = data.get("completed", 0)
                            total = data.get("total", 1) or 1
                            percent = (completed / total * 100) if total else 0
                            async with _llm_pull_tasks_lock:
                                _llm_pull_tasks[key] = _LlmPullTask(
                                    status="pulling" if status != "success" else "complete",
                                    stage=status,
                                    percent=percent,
                                )
                            if status == "success":
                                break
                        except json.JSONDecodeError:
                            pass
            async with _llm_pull_tasks_lock:
                _llm_pull_tasks[key] = _LlmPullTask(status="complete", stage="done", percent=100)
        except Exception as exc:
            logger.exception("Pull failed for Local LLM %s model %s: %s", llm_id, model_name, exc)
            async with _llm_pull_tasks_lock:
                _llm_pull_tasks[key] = _LlmPullTask(status="error", error=str(exc))

    asyncio.create_task(_run())
    return {"status": "accepted", "message": "Pull started. Poll pull-status for progress."}


@router.get("/{llm_id}/ollama/models/{model_name:path}/pull-status")
async def get_local_llm_pull_status(llm_id: str, model_name: str, current_user: str = Depends(get_current_user)):
    """Poll pull progress for a Local LLM."""
    _resolve_local_llm(llm_id, current_user)
    key = (llm_id, model_name)
    async with _llm_pull_tasks_lock:
        task = _llm_pull_tasks.get(key)
    if not task:
        return {"status": "unknown"}
    return {"status": task.status, "stage": task.stage, "percent": task.percent, "error": task.error}


@router.post("/{llm_id}/ollama/models/{model_name:path}/unload")
async def unload_local_llm_model(llm_id: str, model_name: str, current_user: str = Depends(get_current_user)):
    """Unload model from memory for a Local LLM."""
    _, base_url = _resolve_local_llm(llm_id, current_user)
    url = f"{base_url.rstrip('/')}/api/generate"
    headers = _ollama_auth_headers(base_url)
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                url,
                json={"model": model_name, "prompt": ".", "stream": False, "keep_alive": 0},
                headers=headers,
            )
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(502, f"Ollama unload failed: {exc.response.text}")
    return {"status": "unloaded"}
