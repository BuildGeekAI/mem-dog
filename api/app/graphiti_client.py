"""Graphiti temporal knowledge graph — lazy singleton client.

Requires NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD env vars and
SYSTEM_GEMINI_API_KEY for LLM-powered entity/relationship extraction.
"""

import logging
import os

logger = logging.getLogger("mem_dog.graphiti")

_graphiti = None


def is_graphiti_enabled() -> bool:
    """True when Neo4j connection details are configured."""
    return bool(os.getenv("NEO4J_URI"))


async def get_graphiti():
    """Return the Graphiti singleton, creating it on first call.

    Raises RuntimeError if NEO4J_URI is not configured.
    """
    global _graphiti
    if _graphiti is not None:
        return _graphiti

    neo4j_uri = os.getenv("NEO4J_URI")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "")

    if not neo4j_uri:
        raise RuntimeError(
            "Graphiti requires NEO4J_URI to be configured. "
            "Set NEO4J_URI, NEO4J_USER, and NEO4J_PASSWORD env vars."
        )

    from graphiti_core import Graphiti

    # Use Gemini for ALL three providers: LLM, embedder, and cross-encoder (reranker).
    # Graphiti defaults to OpenAI for all three if not explicitly provided,
    # which fails without OPENAI_API_KEY.
    gemini_key = os.getenv("SYSTEM_GEMINI_API_KEY", "")
    llm_client = None
    embedder = None
    cross_encoder = None

    if gemini_key:
        try:
            from graphiti_core.llm_client.gemini_client import GeminiClient
            from graphiti_core.llm_client.config import LLMConfig

            llm_config = LLMConfig(api_key=gemini_key, model="gemini-2.5-flash")
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

    _graphiti = Graphiti(
        neo4j_uri, neo4j_user, neo4j_password,
        llm_client=llm_client, embedder=embedder, cross_encoder=cross_encoder,
    )
    await _graphiti.build_indices_and_constraints()
    logger.info("Graphiti client initialized (neo4j=%s)", neo4j_uri)
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
