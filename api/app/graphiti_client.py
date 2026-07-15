"""Graphiti temporal knowledge graph — lazy singleton client.

Requires NEO4J_URI, NEO4J_USER, and NEO4J_PASSWORD. AI for extraction/search
uses SYSTEM_GEMINI_API_KEY when set, otherwise local Ollama OpenAI-compat
(/v1 chat + embeddings).

When Neo4j is configured but no AI provider is available, Graphiti is
soft-disabled: search returns empty results and ingest/startup log a warning
instead of failing the API process.
"""

from __future__ import annotations

import logging
from typing import Optional, Tuple

from app import config

logger = logging.getLogger("mem_dog.graphiti")

_graphiti = None
# Set after a failed AI resolve / Graphiti construct so callers soft-degrade.
_graphiti_unavailable_reason: Optional[str] = None

# Ollama accepts any non-empty api_key for its OpenAI-compatible API.
_OLLAMA_OPENAI_API_KEY = "ollama"
_DEFAULT_K8S_OLLAMA_BASE = "http://ollama.webhook-pipeline.svc.cluster.local:11434"
_DEFAULT_EMBEDDING_DIM = 768


def is_graphiti_enabled() -> bool:
    """True when Neo4j connection details are configured."""
    return bool(_neo4j_uri())


def graphiti_unavailable_reason() -> Optional[str]:
    """Reason Graphiti was soft-disabled, or None if usable / not yet probed."""
    return _graphiti_unavailable_reason


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


def _build_graphiti_clients() -> Optional[Tuple[object, object, object, str]]:
    """Resolve Graphiti AI clients, or None when none can be initialized."""
    gemini_key = (config.SYSTEM_GEMINI_API_KEY or "").strip()
    if gemini_key:
        llm_client, embedder, cross_encoder = _build_gemini_clients(gemini_key)
        if llm_client is not None and embedder is not None:
            return llm_client, embedder, cross_encoder, "gemini"
        logger.warning(
            "SYSTEM_GEMINI_API_KEY is set but Graphiti Gemini clients failed; "
            "trying local Ollama fallback"
        )

    openai_base = _resolve_ollama_openai_base()
    if openai_base:
        chat_model = (config.MODEL_SERVER_MODEL or "").strip()
        embedding_model = (config.OLLAMA_LOCAL_MODEL_EMBEDDING or "").strip()
        if not chat_model or not embedding_model:
            logger.warning(
                "Local Ollama base %s is set for Graphiti but MODEL_SERVER_MODEL "
                "and OLLAMA_LOCAL_MODEL_EMBEDDING must both be set",
                openai_base,
            )
        else:
            try:
                llm_client, embedder, cross_encoder = _build_ollama_clients(
                    openai_base,
                    chat_model=chat_model,
                    embedding_model=embedding_model,
                )
                return llm_client, embedder, cross_encoder, "ollama_local"
            except Exception as exc:
                logger.warning("Graphiti Ollama clients failed: %s", exc)

    logger.warning(
        "Graphiti soft-disabled: no AI provider. Set SYSTEM_GEMINI_API_KEY or "
        "local Ollama via MODEL_SERVER_URL / OLLAMA_LOCAL_API_BASE with "
        "MODEL_SERVER_MODEL and OLLAMA_LOCAL_MODEL_EMBEDDING."
    )
    return None


async def get_graphiti():
    """Return the Graphiti singleton, or None when soft-disabled.

    Raises RuntimeError only when NEO4J_URI is missing (callers should check
    ``is_graphiti_enabled()`` first). AI / client failures soft-disable Graphiti
    and return None so search/ingest can degrade without 500s.
    """
    global _graphiti, _graphiti_unavailable_reason
    if _graphiti is not None:
        return _graphiti
    if _graphiti_unavailable_reason is not None:
        return None

    import os

    neo4j_uri = _neo4j_uri()
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "")

    if not neo4j_uri:
        raise RuntimeError(
            "Graphiti requires NEO4J_URI to be configured. "
            "Set NEO4J_URI, NEO4J_USER, and NEO4J_PASSWORD env vars."
        )

    clients = _build_graphiti_clients()
    if clients is None:
        _graphiti_unavailable_reason = "no AI provider available"
        return None

    llm_client, embedder, cross_encoder, provider = clients

    try:
        from graphiti_core import Graphiti

        _graphiti = Graphiti(
            neo4j_uri,
            neo4j_user,
            neo4j_password,
            llm_client=llm_client,
            embedder=embedder,
            cross_encoder=cross_encoder,
        )
        await _graphiti.build_indices_and_constraints()
    except Exception as exc:
        _graphiti = None
        _graphiti_unavailable_reason = str(exc)
        logger.warning("Graphiti soft-disabled after init failure: %s", exc)
        return None

    logger.info(
        "Graphiti client initialized (neo4j=%s, provider=%s)",
        neo4j_uri,
        provider,
    )
    return _graphiti


def build_valid_at_search_filter(at):
    """Build a Graphiti SearchFilters for facts valid at *at* (datetime).

    Returns None when *at* is falsy.
    """
    if not at:
        return None
    from graphiti_core.search.search_filters import (
        ComparisonOperator,
        DateFilter,
        SearchFilters,
    )

    return SearchFilters(
        valid_at=[
            [
                DateFilter(
                    date=at,
                    comparison_operator=ComparisonOperator.less_than_equal,
                )
            ]
        ]
    )


def build_temporal_search_filter(
    *,
    valid_at=None,
    valid_after=None,
    valid_before=None,
):
    """Build SearchFilters from optional temporal datetime bounds."""
    from graphiti_core.search.search_filters import (
        ComparisonOperator,
        DateFilter,
        SearchFilters,
    )

    date_filters = []
    if valid_at is not None:
        date_filters.append(
            DateFilter(
                date=valid_at,
                comparison_operator=ComparisonOperator.less_than_equal,
            )
        )
    if valid_after is not None:
        date_filters.append(
            DateFilter(
                date=valid_after,
                comparison_operator=ComparisonOperator.greater_than_equal,
            )
        )
    if valid_before is not None:
        date_filters.append(
            DateFilter(
                date=valid_before,
                comparison_operator=ComparisonOperator.less_than_equal,
            )
        )
    if not date_filters:
        return None
    return SearchFilters(valid_at=[date_filters])


async def search_edges(
    query: str,
    *,
    limit: int = 10,
    search_filter=None,
):
    """Hybrid edge search via Graphiti's current ``search()`` API.

    Returns an empty list when Graphiti is soft-disabled.

    Current graphiti_core exposes:
      search(query, num_results=…, search_filter=…) -> list[EntityEdge]
    """
    graphiti = await get_graphiti()
    if graphiti is None:
        logger.debug(
            "Graphiti search skipped (%s)",
            _graphiti_unavailable_reason or "unavailable",
        )
        return []
    kwargs: dict = {"query": query, "num_results": limit}
    if search_filter is not None:
        kwargs["search_filter"] = search_filter
    return await graphiti.search(**kwargs)


async def close_graphiti():
    """Close the Graphiti client and Neo4j driver."""
    global _graphiti, _graphiti_unavailable_reason
    if _graphiti is not None:
        try:
            await _graphiti.close()
            logger.info("Graphiti client closed")
        except Exception as exc:
            logger.warning("Error closing Graphiti: %s", exc)
        _graphiti = None
    _graphiti_unavailable_reason = None
