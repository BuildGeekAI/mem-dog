"""Graphiti temporal knowledge graph — lazy singleton client.

Requires NEO4J_URI, NEO4J_USER, and NEO4J_PASSWORD. AI for extraction/search
uses SYSTEM_GEMINI_API_KEY when set, otherwise local Ollama OpenAI-compat
(/v1 chat + embeddings).
"""

from __future__ import annotations

import logging
from typing import Optional, Tuple

from app import config

logger = logging.getLogger("mem_dog.graphiti")

_graphiti = None

# Ollama accepts any non-empty api_key for its OpenAI-compatible API.
_OLLAMA_OPENAI_API_KEY = "ollama"
_DEFAULT_K8S_OLLAMA_BASE = "http://ollama.webhook-pipeline.svc.cluster.local:11434"
_DEFAULT_EMBEDDING_DIM = 768


def is_graphiti_enabled() -> bool:
    """True when Neo4j connection details are configured."""
    return bool(_neo4j_uri())


def _neo4j_uri() -> str:
    import os

    return (os.getenv("NEO4J_URI") or "").strip()


def _resolve_ollama_openai_base() -> Optional[str]:
    """Return Ollama OpenAI base URL (…/v1) when local inference is configured."""
    base = (
        config.MODEL_SERVER_URL
        or config.MODEL_SERVER_URL_MEDIUM
        or config.MODEL_SERVER_URL_SMALL
        or config.MODEL_SERVER_URL_LARGE
        or ""
    ).rstrip("/")

    if not base and config.OLLAMA_LOCAL_API_BASE:
        local = config.OLLAMA_LOCAL_API_BASE.rstrip("/")
        if config.OLLAMA_TIER or local != _DEFAULT_K8S_OLLAMA_BASE.rstrip("/"):
            base = local

    if not base:
        return None
    return base if base.endswith("/v1") else f"{base}/v1"


def _build_gemini_clients(
    gemini_key: str,
) -> Tuple[object, object, Optional[object]]:
    """Build Gemini LLM, embedder, and reranker clients."""
    from graphiti_core.llm_client.config import LLMConfig

    llm_client = None
    embedder = None
    cross_encoder = None
    llm_config = LLMConfig(api_key=gemini_key, model="gemini-2.5-flash")

    try:
        from graphiti_core.llm_client.gemini_client import GeminiClient

        llm_client = GeminiClient(llm_config)
    except (ImportError, Exception) as exc:
        logger.warning("Gemini LLM client not available: %s", exc)

    try:
        from graphiti_core.embedder.gemini import GeminiEmbedder, GeminiEmbedderConfig

        embedder = GeminiEmbedder(
            GeminiEmbedderConfig(api_key=gemini_key, model="gemini-embedding-001")
        )
    except (ImportError, Exception) as exc:
        logger.warning("Gemini embedder not available: %s", exc)

    try:
        from graphiti_core.cross_encoder.gemini_reranker_client import GeminiRerankerClient

        cross_encoder = GeminiRerankerClient(llm_config)
    except (ImportError, Exception) as exc:
        logger.warning("Gemini reranker not available: %s", exc)

    return llm_client, embedder, cross_encoder


def _build_ollama_clients(
    openai_base: str,
    *,
    chat_model: str,
    embedding_model: str,
    embedding_dim: int = _DEFAULT_EMBEDDING_DIM,
) -> Tuple[object, object, object]:
    """Build OpenAI-compatible clients pointed at local Ollama."""
    from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient
    from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
    from graphiti_core.llm_client.config import LLMConfig
    from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient

    llm_config = LLMConfig(
        api_key=_OLLAMA_OPENAI_API_KEY,
        model=chat_model,
        base_url=openai_base,
    )
    llm_client = OpenAIGenericClient(llm_config)
    embedder = OpenAIEmbedder(
        OpenAIEmbedderConfig(
            api_key=_OLLAMA_OPENAI_API_KEY,
            base_url=openai_base,
            embedding_model=embedding_model,
            embedding_dim=embedding_dim,
        )
    )
    cross_encoder = OpenAIRerankerClient(llm_config)
    return llm_client, embedder, cross_encoder


def _build_graphiti_clients() -> Tuple[object, object, object, str]:
    """Resolve Graphiti AI clients. Raises RuntimeError when none are configured."""
    gemini_key = (config.SYSTEM_GEMINI_API_KEY or "").strip()
    if gemini_key:
        llm_client, embedder, cross_encoder = _build_gemini_clients(gemini_key)
        if llm_client is None or embedder is None:
            raise RuntimeError(
                "SYSTEM_GEMINI_API_KEY is set but Graphiti Gemini clients failed to initialize."
            )
        return llm_client, embedder, cross_encoder, "gemini"

    openai_base = _resolve_ollama_openai_base()
    if openai_base:
        chat_model = (config.MODEL_SERVER_MODEL or "").strip()
        embedding_model = (config.OLLAMA_LOCAL_MODEL_EMBEDDING or "").strip()
        if not chat_model or not embedding_model:
            raise RuntimeError(
                "Local Ollama is configured for Graphiti but MODEL_SERVER_MODEL and "
                "OLLAMA_LOCAL_MODEL_EMBEDDING must both be set."
            )
        llm_client, embedder, cross_encoder = _build_ollama_clients(
            openai_base,
            chat_model=chat_model,
            embedding_model=embedding_model,
        )
        return llm_client, embedder, cross_encoder, "ollama_local"

    raise RuntimeError(
        "Graphiti requires an AI provider. Set SYSTEM_GEMINI_API_KEY or configure "
        "local Ollama via MODEL_SERVER_URL / OLLAMA_LOCAL_API_BASE with "
        "MODEL_SERVER_MODEL and OLLAMA_LOCAL_MODEL_EMBEDDING."
    )


async def get_graphiti():
    """Return the Graphiti singleton, creating it on first call.

    Raises RuntimeError if NEO4J_URI is not configured or no AI provider is available.
    """
    global _graphiti
    if _graphiti is not None:
        return _graphiti

    import os

    neo4j_uri = _neo4j_uri()
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "")

    if not neo4j_uri:
        raise RuntimeError(
            "Graphiti requires NEO4J_URI to be configured. "
            "Set NEO4J_URI, NEO4J_USER, and NEO4J_PASSWORD env vars."
        )

    from graphiti_core import Graphiti

    llm_client, embedder, cross_encoder, provider = _build_graphiti_clients()

    _graphiti = Graphiti(
        neo4j_uri,
        neo4j_user,
        neo4j_password,
        llm_client=llm_client,
        embedder=embedder,
        cross_encoder=cross_encoder,
    )
    await _graphiti.build_indices_and_constraints()
    logger.info(
        "Graphiti client initialized (neo4j=%s, provider=%s)",
        neo4j_uri,
        provider,
    )
    return _graphiti


async def close_graphiti():
    """Close the Graphiti client and Neo4j driver."""
    global _graphiti
    if _graphiti is not None:
        try:
            await _graphiti.close()
            logger.info("Graphiti client closed")
        except Exception as exc:
            logger.warning("Error closing Graphiti: %s", exc)
        _graphiti = None
