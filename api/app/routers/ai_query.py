"""AI Query router — proxies requests to the model server (Cloud Run B).

Endpoints
---------
POST /api/v1/ai/query                       Query one or more data items with
                                            natural language (fetches content,
                                            builds context, calls model server).
POST /api/v1/ai/query/semantic              Semantic (embedding) search using
                                            pgvector similarity.  Returns the
                                            most relevant stored chunks and
                                            optionally synthesises an answer.
POST /api/v1/ai/query/chat                  Conversational RAG with inline
                                            citations [1][2] linking to sources.
POST /api/v1/ai/query/timeline              Query a set of timeline data items.
POST /api/v1/ai/query/test                  Configuration status probe.

All inference endpoints require MODEL_SERVER_URL to be configured.  When the
model server is unavailable the endpoints return 503.
The /semantic endpoint requires SYSTEM_GEMINI_API_KEY (or a
configured embedding engine) to generate the query vector.
"""

import asyncio
import logging
import os
import re
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from fastapi import Request as FastAPIRequest

from app import config
from app.gcp_auth import get_identity_token_for_url
from app.storage import get_storage

logger = logging.getLogger("mem_dog.ai_query")

router = APIRouter(prefix="/api/v1/ai/query", tags=["AI Query"])

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _model_server_client(tier: str = "medium") -> httpx.AsyncClient:
    """Return a pre-configured async HTTP client for *tier*'s model server."""
    url = config.get_model_server_url(tier)
    headers = {}
    token = get_identity_token_for_url(url)
    if token:
        headers["Authorization"] = f"Bearer {token}"

    return httpx.AsyncClient(
        base_url=url,
        timeout=config.MODEL_SERVER_TIMEOUT_S,
        headers=headers,
    )


def _require_model_server() -> None:
    """Raise 503 if MODEL_SERVER_URL is not configured."""
    if not config.is_model_server_enabled():
        raise HTTPException(
            status_code=503,
            detail=(
                "Model server is not configured. "
                "Set MODEL_SERVER_URL to the URL of the Ollama server."
            ),
        )


def _convert_multimodal_to_text(messages: list[dict]) -> list[dict]:
    """
    Convert multimodal content (text + image parts) to plain text.
    Tier and local models are typically text-only; image_url parts cause crashes.
    Replaces image parts with a placeholder so the model receives text-only.
    """
    out = []
    for msg in messages:
        content = msg.get("content")
        if isinstance(content, list):
            parts = []
            for p in content:
                if isinstance(p, dict):
                    if p.get("type") == "text" and p.get("text"):
                        parts.append(p["text"])
                    elif p.get("type") == "image_url":
                        parts.append("[Image attached]")
            msg = {**msg, "content": " ".join(parts) or "[Image attached]"}
        out.append(msg)
    return out


def _sanitize_messages(messages: list[dict]) -> list[dict]:
    """
    Sanitize messages for models that don't support system roles.
    Merges system prompt into the first user message.
    Handles both string content and multimodal content (list of text/image parts).
    """
    sanitized = []
    system_content = []

    for msg in messages:
        if msg["role"] == "system":
            content = msg["content"]
            system_content.append(content if isinstance(content, str) else "")
        else:
            sanitized.append(msg)

    if system_content:
        full_system_prompt = "\n\n".join(system_content)

        for i, msg in enumerate(sanitized):
            if msg["role"] == "user":
                content = msg["content"]
                if isinstance(content, str):
                    sanitized[i] = {
                        "role": "user",
                        "content": f"{full_system_prompt}\n\n{content}",
                    }
                elif isinstance(content, list):
                    # Multimodal: prepend system prompt to first text part
                    new_parts = list(content)
                    for j, part in enumerate(new_parts):
                        if isinstance(part, dict) and part.get("type") == "text":
                            new_parts[j] = {
                                **part,
                                "text": f"{full_system_prompt}\n\n{part.get('text', '')}",
                            }
                            break
                    else:
                        new_parts.insert(0, {"type": "text", "text": full_system_prompt})
                    sanitized[i] = {"role": "user", "content": new_parts}
                break
        else:
            sanitized.insert(0, {"role": "user", "content": full_system_prompt})

    return sanitized


async def _get_ollama_model_for_tier(tier: str) -> str:
    """When OLLAMA_TIER=true, resolve model name: first loaded via /api/ps, else default."""
    url = config.get_model_server_url(tier)
    try:
        async with httpx.AsyncClient(base_url=url, timeout=5) as client:
            resp = await client.get("/api/ps")
        resp.raise_for_status()
        data = resp.json()
        models = data.get("models") or []
        if models and len(models) > 0:
            return models[0].get("name") or config.MODEL_SERVER_MODEL
    except Exception:
        pass
    return config.MODEL_SERVER_MODEL


async def _chat_completion(
    messages: list[dict],
    max_tokens: int = 512,
    temperature: float = 0.7,
    tier: str = "medium",
) -> dict[str, Any]:
    """Smart-routed chat completion: local Ollama primary → Gemini fallback.

    Uses the smart routing configuration to determine which models to use.
    Local Ollama is the primary with a shorter timeout (default 45s) so
    we can fall back to Gemini before the GKE gateway drops the connection.
    Records token telemetry on success.
    """

    # Sanitize messages to avoid "ValueError: System role not supported"
    sanitized_messages = _sanitize_messages(messages)

    model_name = config.MODEL_SERVER_MODEL
    if config.OLLAMA_TIER:
        model_name = await _get_ollama_model_for_tier(tier)

    # Shorter timeout for primary so we can fall back before GKE gateway (~60s).
    chat_timeout = min(int(os.getenv("CHAT_COMPLETION_TIMEOUT_S", "15")), config.MODEL_SERVER_TIMEOUT_S)

    t0 = time.monotonic()

    # --- Primary: local Ollama ---
    try:
        url = config.get_model_server_url(tier)
        headers: dict[str, str] = {}
        token = get_identity_token_for_url(url)
        if token:
            headers["Authorization"] = f"Bearer {token}"
        async with httpx.AsyncClient(base_url=url, timeout=chat_timeout, headers=headers) as client:
            resp = await client.post(
                "/v1/chat/completions",
                json={
                    "model": model_name,
                    "messages": sanitized_messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
            )
        resp.raise_for_status()
        result = resp.json()
        return result
    except Exception as ollama_err:
        latency = int((time.monotonic() - t0) * 1000)
        logger.info("Local Ollama failed after %dms (%s), falling back to Gemini", latency, ollama_err)

    # --- Fallback: Gemini ---
    if not config.SYSTEM_GEMINI_API_KEY:
        raise RuntimeError(f"Local Ollama failed and no Gemini API key configured: {ollama_err}")

    return await _gemini_chat_completion(messages, max_tokens, temperature)


async def _gemini_chat_completion(
    messages: list[dict],
    max_tokens: int = 512,
    temperature: float = 0.7,
) -> dict[str, Any]:
    """Gemini REST API fallback for chat completion."""
    model = config.SYSTEM_GEMINI_MODEL_COMPLETION
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={config.SYSTEM_GEMINI_API_KEY}"
    )

    # Convert OpenAI-style messages to Gemini contents format
    contents: list[dict] = []
    system_text = ""
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "system":
            system_text += content + "\n"
        else:
            gemini_role = "model" if role == "assistant" else "user"
            contents.append({"role": gemini_role, "parts": [{"text": content}]})

    body: dict[str, Any] = {
        "contents": contents,
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "temperature": temperature,
        },
    }
    if system_text.strip():
        body["systemInstruction"] = {"parts": [{"text": system_text.strip()}]}

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(url, json=body)
    resp.raise_for_status()
    data = resp.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"]

    usage_meta = data.get("usageMetadata", {})
    prompt_tokens = usage_meta.get("promptTokenCount", 0)
    completion_tokens = usage_meta.get("candidatesTokenCount", 0)

    # Return in OpenAI-compatible format
    return {
        "choices": [{"message": {"role": "assistant", "content": text}}],
        "model": model,
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class DataQueryRequest(BaseModel):
    query: str
    data_ids: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    max_tokens: int = Field(512, ge=1, le=4096)
    temperature: float = Field(0.3, ge=0.0, le=2.0)
    user: str = config.DEFAULT_USER_ID


class DataQuerySource(BaseModel):
    data_id: str
    relevance: float = 0.5


class DataQueryResponse(BaseModel):
    query: str
    response: str
    sources: list[DataQuerySource] = []
    model: str
    model_server_url: str
    latency_ms: int


class TimelineQueryRequest(BaseModel):
    query: str
    timeline_data_ids: list[str] = Field(default_factory=list)
    max_tokens: int = Field(512, ge=1, le=4096)
    temperature: float = Field(0.3, ge=0.0, le=2.0)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("", response_model=DataQueryResponse)
async def query_data(request: DataQueryRequest):
    """Query one or more data items using natural language.

    Fetches the raw content of each ``data_id`` from storage, builds a context
    prompt, and forwards it to the model server.  Useful for asking questions
    about stored documents, logs, or structured data.

    Example::

        POST /api/v1/ai/query
        {
          "query": "What are the main topics in this document?",
          "data_ids": ["abc123"],
          "max_tokens": 512
        }
    """
    _require_model_server()

    # Fetch content for each data_id
    context_parts: list[str] = []
    found_ids: list[str] = []

    if request.data_ids:
        try:
            storage = get_storage()
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"Storage unavailable: {exc}")

        for data_id in request.data_ids[:10]:
            try:
                raw = storage.get_data(data_id)
                if isinstance(raw, bytes):
                    text = raw.decode("utf-8", errors="replace")
                else:
                    text = str(raw)
                # Truncate very large items to fit in context
                if len(text) > 3000:
                    text = text[:3000] + "\n...[truncated]"
                context_parts.append(f"[Data {data_id[:12]}]\n{text}")
                found_ids.append(data_id)
            except Exception as exc:
                logger.warning("Could not fetch data_id=%s: %s", data_id, exc)

    if context_parts:
        context_block = "\n\n---\n\n".join(context_parts)
        system_prompt = (
            "You are a helpful assistant that answers questions about the following data. "
            "Be concise and accurate. If the answer is not in the provided data, say so."
        )
        user_content = f"Data context:\n\n{context_block}\n\n---\n\nQuestion: {request.query}"
    else:
        system_prompt = "You are a helpful assistant."
        user_content = request.query

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    t0 = time.monotonic()
    try:
        result = await _chat_completion(
            messages=messages,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
        )
    except httpx.HTTPStatusError as exc:
        logger.error("Model server returned %s", exc.response.status_code)
        raise HTTPException(status_code=502, detail=f"Model server error: {exc.response.status_code}")
    except httpx.RequestError as exc:
        logger.error("Model server request failed: %s", exc)
        raise HTTPException(status_code=503, detail="Model server is unreachable")

    latency_ms = int((time.monotonic() - t0) * 1000)
    response_text: str = result["choices"][0]["message"]["content"].strip()

    logger.info(
        "query_data | data_ids=%d latency_ms=%d",
        len(found_ids), latency_ms,
    )

    sources = [DataQuerySource(data_id=did, relevance=0.9) for did in found_ids]

    return DataQueryResponse(
        query=request.query,
        response=response_text,
        sources=sources,
        model=result.get("model", config.MODEL_SERVER_MODEL),
        model_server_url=config.MODEL_SERVER_URL,
        latency_ms=latency_ms,
    )


@router.post("/timeline", response_model=DataQueryResponse)
async def query_timeline(request: TimelineQueryRequest):
    """Query a collection of timeline data items using natural language.

    Delegates to ``query_data`` with the provided ``timeline_data_ids`` as
    the ``data_ids`` list.
    """
    return await query_data(
        DataQueryRequest(
            query=request.query,
            data_ids=request.timeline_data_ids,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
        )
    )


@router.post("/test")
async def test_ai_engine():
    """Return configuration status for the AI query layer."""
    return {
        "model_server_enabled": config.is_model_server_enabled(),
        "model_server_url": config.MODEL_SERVER_URL or None,
        "model_server_model": config.MODEL_SERVER_MODEL,
        "ai_enabled": config.is_ai_enabled(),
        "system_ai_available": config.is_system_ai_available(),
        "postgres_enabled": config.is_postgres_enabled(),
        "status": "ok" if config.is_model_server_enabled() else "model_server_not_configured",
    }


# ---------------------------------------------------------------------------
# Semantic search (pgvector)
# ---------------------------------------------------------------------------

class SearchMode(str, Enum):
    vector = "vector"      # cosine only (default, backward compat)
    fts = "fts"            # BM25 text only
    hybrid = "hybrid"      # pgvector cosine + BM25 via RRF
    graph = "graph"        # Graphiti search (BFS + semantic + BM25 on knowledge graph)
    full = "full"          # All signals: pgvector hybrid + Graphiti graph, merged with RRF


class RerankMethod(str, Enum):
    none = "none"
    rrf = "rrf"
    mmr = "mmr"
    cross_encoder = "cross_encoder"


class RerankConfig(BaseModel):
    method: RerankMethod = RerankMethod.none
    mmr_lambda: float = Field(0.5, ge=0.0, le=1.0)
    cross_encoder_tier: str = "small"


class TemporalFilter(BaseModel):
    valid_at: datetime | None = None
    valid_after: datetime | None = None
    valid_before: datetime | None = None


class SemanticQueryRequest(BaseModel):
    query: str = Field(..., description="Natural language question or search string")
    max_results: int = Field(5, ge=1, le=20)
    search_mode: SearchMode = Field(SearchMode.vector, description="Search strategy")
    vector_weight: float = Field(0.5, ge=0.0, le=1.0, description="Weight for vector similarity in hybrid mode")
    fts_weight: float = Field(0.5, ge=0.0, le=1.0, description="Weight for BM25 text match in hybrid mode")
    rerank: RerankConfig = Field(default_factory=RerankConfig, description="Reranking configuration")
    temporal: TemporalFilter | None = Field(None, description="Temporal filter for graph search")
    synthesise: bool = Field(
        False,
        description="When True, pass the top chunks to the model server and return a synthesised answer",
    )
    model_tier: str = Field("medium", pattern="^(small|medium|large|very-large)$")
    user_id: str = Field("", description="Scope results to this user")


class SemanticResult(BaseModel):
    embedding_id: str
    data_id: str
    chunk_text: str
    similarity: float


class SemanticMatchChunk(BaseModel):
    embedding_id: str
    chunk_text: str
    similarity: float
    fts_rank: float | None = None
    rrf_score: float | None = None
    search_type: str | None = None


class SemanticRecord(BaseModel):
    data_id: str
    name: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    mime_type: str | None = None
    created_at: str | None = None
    address: str | None = None
    best_similarity: float
    matching_chunks: list[SemanticMatchChunk]


class SemanticQueryResponse(BaseModel):
    query: str
    records: list[SemanticRecord]
    answer: str | None = None
    model: str | None = None
    latency_ms: int


@router.post("/semantic", response_model=SemanticQueryResponse)
async def semantic_query(request: SemanticQueryRequest, http_request: FastAPIRequest = None):
    """Semantic search over stored embeddings using cosine similarity.

    Embeds the query string with the same engine used when embeddings were
    created (system Gemini by default), then runs similarity search over
    blob-store embeddings. When ``synthesise`` is True the top chunks are
    forwarded to the model server to produce a natural-language answer.

    Requires SYSTEM_GEMINI_API_KEY or a configured embedding engine.
    """
    t0 = time.monotonic()

    if not config.is_ai_enabled():
        raise HTTPException(
            status_code=503,
            detail="AI layer is not enabled. Configure SYSTEM_GEMINI_API_KEY or an embedding engine.",
        )

    storage = get_storage()

    # 1. Embed the query (use RETRIEVAL_QUERY task type for search queries)
    try:
        engine_type, model, api_key = storage._resolve_embedding_engine(None)
        from app.storage import _generate_embeddings
        query_vectors = _generate_embeddings(
            [request.query], engine_type, model, api_key,
            task_type="RETRIEVAL_QUERY",
        )
        query_vector = query_vectors[0]
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Failed to embed query: {exc}")

    # Resolve user_id: prefer body param, fall back to authenticated user from JWT/API key
    user_id = (request.user_id or "").strip()
    if not user_id and http_request:
        user_id = getattr(http_request.state, "user_id", "") or ""
    if user_id:
        try:
            from app.models import TokenUsageRecord
            emb_tokens = len(request.query.split())
            storage.record_token_usage(TokenUsageRecord(
                user_id=user_id,
                prompt_tokens=emb_tokens,
                completion_tokens=0,
                total_tokens=emb_tokens,
                model=f"embedding/{model}",
                agent_type="semantic-embedding",
            ))
        except Exception:
            pass

    # 2. Search — branch on search_mode
    search_mode = request.search_mode
    raw_results: list = []
    dict_results: list[dict] = []

    try:
        if search_mode == SearchMode.fts:
            dict_results = storage.fts_search(request.query, limit=request.max_results, user_id=user_id)
        elif search_mode == SearchMode.hybrid:
            dict_results = storage.hybrid_search(
                query_vector, request.query, limit=request.max_results,
                user_id=user_id, vector_weight=request.vector_weight, fts_weight=request.fts_weight,
            )
        elif search_mode == SearchMode.graph:
            dict_results = await _graphiti_search(request.query, user_id, request.max_results, request.temporal)
        elif search_mode == SearchMode.full:
            pgvector_task = asyncio.create_task(asyncio.to_thread(
                storage.hybrid_search, query_vector, request.query,
                request.max_results, user_id, "", request.vector_weight, request.fts_weight,
            ))
            graphiti_results = await _graphiti_search(request.query, user_id, request.max_results, request.temporal)
            pgvector_results = await pgvector_task
            from app.reranker import rrf_merge
            dict_results = rrf_merge(pgvector_results, graphiti_results)[:request.max_results]
        else:
            # Default: vector-only (backward compatible)
            raw_results = storage.similarity_search(
                query_vector, limit=request.max_results, user_id=user_id,
            )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Search failed: {exc}")

    # Apply reranking
    if dict_results and request.rerank.method != RerankMethod.none:
        from app.reranker import mmr_rerank, cross_encoder_rerank
        if request.rerank.method == RerankMethod.mmr:
            dict_results = mmr_rerank(dict_results, query_vector, lambda_param=request.rerank.mmr_lambda, top_k=request.max_results)
        elif request.rerank.method == RerankMethod.cross_encoder:
            model_url = config.get_model_server_url(request.rerank.cross_encoder_tier)
            dict_results = await cross_encoder_rerank(request.query, dict_results, model_url, top_k=request.max_results)

    # 3. Group raw results by data_id and enrich with record metadata
    from collections import OrderedDict
    grouped: OrderedDict[str, list] = OrderedDict()

    # Normalize: if we have dict_results (from hybrid/fts/graph), convert to grouped chunks
    if dict_results:
        for r in dict_results:
            data_id = r.get("data_id", "")
            grouped.setdefault(data_id, []).append(
                SemanticMatchChunk(
                    embedding_id=r.get("embedding_id", ""),
                    chunk_text=r.get("chunk_text", ""),
                    similarity=round(r.get("similarity", 0.0), 4),
                    fts_rank=round(r["fts_rank"], 4) if r.get("fts_rank") is not None else None,
                    rrf_score=round(r["rrf_score"], 6) if r.get("rrf_score") is not None else None,
                    search_type=r.get("search_type"),
                )
            )
    else:
        for r in raw_results:
            emb_id, data_id, chunk_text, similarity = r
            grouped.setdefault(data_id, []).append(
                SemanticMatchChunk(
                    embedding_id=emb_id,
                    chunk_text=chunk_text,
                    similarity=round(similarity, 4),
                )
            )

    records: list[SemanticRecord] = []
    for data_id, chunks in grouped.items():
        best_sim = max(c.similarity for c in chunks)
        # Fetch metadata for enrichment
        meta = None
        try:
            meta = storage.get_metadata(data_id, user_id=user_id or None)
        except Exception:
            pass
        records.append(SemanticRecord(
            data_id=data_id,
            name=getattr(meta, "name", None) if meta else None,
            description=getattr(meta, "description", None) if meta else None,
            tags=getattr(meta, "tags", None) if meta else None,
            mime_type=getattr(meta, "content_type", None) if meta else None,
            created_at=getattr(meta, "created_at", None) if meta else None,
            address=getattr(meta, "address", None) if meta else None,
            best_similarity=best_sim,
            matching_chunks=chunks,
        ))
    records.sort(key=lambda r: r.best_similarity, reverse=True)

    # 4. Optionally synthesise an answer via the model server
    answer: str | None = None
    used_model: str | None = None
    if request.synthesise and records:
        _require_model_server()
        context_chunks = "\n\n---\n\n".join(
            f"[{rec.name or rec.data_id[:12]}] {chunk.chunk_text}"
            for rec in records
            for chunk in rec.matching_chunks
        )
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a helpful assistant. Answer the question using ONLY "
                    "the provided context chunks. Be concise and accurate."
                ),
            },
            {
                "role": "user",
                "content": f"Context:\n\n{context_chunks}\n\n---\n\nQuestion: {request.query}",
            },
        ]
        try:
            result = await _chat_completion(
                messages=messages,
                max_tokens=512,
                temperature=0.3,
                tier=request.model_tier,
            )
            answer = result["choices"][0]["message"]["content"].strip()
            used_model = result.get("model") or config.get_model_label(request.model_tier)
            # Record synthesis token usage
            if user_id:
                try:
                    from app.models import TokenUsageRecord
                    s_usage = result.get("usage", {})
                    s_total = s_usage.get("total_tokens", s_usage.get("prompt_tokens", 0) + s_usage.get("completion_tokens", 0))
                    storage.record_token_usage(TokenUsageRecord(
                        user_id=user_id,
                        prompt_tokens=s_usage.get("prompt_tokens", 0),
                        completion_tokens=s_usage.get("completion_tokens", 0),
                        total_tokens=s_total,
                        model=used_model,
                        agent_type="semantic-synthesis",
                    ))
                except Exception:
                    pass
        except Exception as exc:
            logger.warning("Synthesis failed: %s", exc)
            answer = None

    latency_ms = int((time.monotonic() - t0) * 1000)
    logger.info(
        "semantic_query | records=%d synthesise=%s latency_ms=%d",
        len(records),
        request.synthesise,
        latency_ms,
    )

    return SemanticQueryResponse(
        query=request.query,
        records=records,
        answer=answer,
        model=used_model,
        latency_ms=latency_ms,
    )


# ---------------------------------------------------------------------------
# Chat with Data — conversational RAG with inline citations
# ---------------------------------------------------------------------------


class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = Field(default_factory=list)
    max_results: int = Field(5, ge=1, le=20)
    max_tokens: int = Field(1024, ge=1, le=4096)
    temperature: float = Field(0.3, ge=0.0, le=2.0)
    model_tier: str = Field("medium", pattern="^(small|medium|large|very-large)$")
    user_id: str = Field("")
    memory_id: Optional[str] = Field(None)
    search_mode: SearchMode = Field(SearchMode.vector, description="Search strategy")
    vector_weight: float = Field(0.5, ge=0.0, le=1.0)
    fts_weight: float = Field(0.5, ge=0.0, le=1.0)
    rerank: RerankConfig = Field(default_factory=RerankConfig)
    temporal: TemporalFilter | None = None


class ChatCitation(BaseModel):
    index: int
    data_id: str
    name: str | None = None
    chunk_text: str
    similarity: float


class ChatResponse(BaseModel):
    answer: str
    citations: list[ChatCitation]
    model: str | None = None
    latency_ms: int


@router.post("/chat", response_model=ChatResponse)
async def chat_with_data(request: ChatRequest, http_request: FastAPIRequest = None):
    """Conversational RAG — answer questions with inline [1][2] citations.

    Embeds the user message, retrieves relevant chunks via similarity search,
    builds a numbered context, and asks the model to answer citing sources.
    Only citations actually referenced in the answer are returned.
    """
    t0 = time.monotonic()

    if not config.is_ai_enabled():
        raise HTTPException(
            status_code=503,
            detail="AI layer is not enabled. Configure SYSTEM_GEMINI_API_KEY or an embedding engine.",
        )
    _require_model_server()

    storage = get_storage()

    # 1. Embed the user message
    try:
        engine_type, model, api_key = storage._resolve_embedding_engine(None)
        from app.storage import _generate_embeddings
        query_vectors = _generate_embeddings(
            [request.message], engine_type, model, api_key,
            task_type="RETRIEVAL_QUERY",
        )
        query_vector = query_vectors[0]
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Failed to embed query: {exc}")

    # Resolve user_id: prefer body param, fall back to authenticated user from JWT/API key
    user_id = (request.user_id or "").strip()
    if not user_id and http_request:
        user_id = getattr(http_request.state, "user_id", "") or ""
    if user_id:
        try:
            from app.models import TokenUsageRecord
            emb_tokens = len(request.message.split())  # approximate
            storage.record_token_usage(TokenUsageRecord(
                user_id=user_id,
                prompt_tokens=emb_tokens,
                completion_tokens=0,
                total_tokens=emb_tokens,
                model=f"embedding/{model}",
                agent_type="chat-embedding",
            ))
        except Exception as tok_err:
            logger.debug("Failed to record embedding token usage: %s", tok_err)

    # 2. Search — branch on search_mode
    search_mode = request.search_mode
    raw_results: list = []
    dict_results: list[dict] = []
    memory_id = request.memory_id or ""

    try:
        if search_mode == SearchMode.fts:
            dict_results = storage.fts_search(request.message, limit=request.max_results, user_id=user_id, memory_id=memory_id)
        elif search_mode == SearchMode.hybrid:
            dict_results = storage.hybrid_search(
                query_vector, request.message, limit=request.max_results,
                user_id=user_id, memory_id=memory_id,
                vector_weight=request.vector_weight, fts_weight=request.fts_weight,
            )
        elif search_mode == SearchMode.graph:
            dict_results = await _graphiti_search(request.message, user_id, request.max_results, request.temporal)
        elif search_mode == SearchMode.full:
            pgvector_task = asyncio.create_task(asyncio.to_thread(
                storage.hybrid_search, query_vector, request.message,
                request.max_results, user_id, memory_id, request.vector_weight, request.fts_weight,
            ))
            graphiti_results = await _graphiti_search(request.message, user_id, request.max_results, request.temporal)
            pgvector_results = await pgvector_task
            from app.reranker import rrf_merge
            dict_results = rrf_merge(pgvector_results, graphiti_results)[:request.max_results]
        else:
            raw_results = storage.similarity_search(
                query_vector, limit=request.max_results, user_id=user_id,
                memory_id=memory_id,
            )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Search failed: {exc}")

    # Apply reranking
    if dict_results and request.rerank.method != RerankMethod.none:
        from app.reranker import mmr_rerank, cross_encoder_rerank
        if request.rerank.method == RerankMethod.mmr:
            dict_results = mmr_rerank(dict_results, query_vector, lambda_param=request.rerank.mmr_lambda, top_k=request.max_results)
        elif request.rerank.method == RerankMethod.cross_encoder:
            model_url = config.get_model_server_url(request.rerank.cross_encoder_tier)
            dict_results = await cross_encoder_rerank(request.message, dict_results, model_url, top_k=request.max_results)

    # Normalize dict_results to raw_results format for downstream processing
    if dict_results:
        raw_results = [
            (r.get("embedding_id", ""), r.get("data_id", ""), r.get("chunk_text", ""), r.get("similarity", 0.0))
            for r in dict_results
        ]

    # 2b. Entity-aware search — find entities mentioned in the query and
    #     boost results whose data_ids are linked to those entities.
    entity_hints: list[str] = []
    try:
        matched_entities = storage.search_entities(request.message, user_id, limit=5)
        if matched_entities:
            entity_data_ids = storage.find_related_data_ids(
                [e["entity_id"] for e in matched_entities], user_id, limit=20,
            )
            existing_data_ids = {did for _, did, _, _ in raw_results}
            for eid in entity_data_ids:
                if eid not in existing_data_ids:
                    try:
                        extra = storage.similarity_search(
                            query_vector, limit=1, user_id=user_id, memory_id="",
                        )
                    except Exception:
                        pass
            entity_hints = [
                f"{e.get('entity_name', '')} ({e.get('entity_type', '')})"
                for e in matched_entities[:5]
            ]
    except Exception as exc:
        logger.debug("Entity-aware search enhancement skipped: %s", exc)

    # 3. Build numbered context with metadata enrichment
    numbered_sources: list[dict] = []
    seen_chunks: set[str] = set()
    for emb_id, data_id, chunk_text, similarity in raw_results:
        chunk_key = f"{data_id}:{chunk_text[:100]}"
        if chunk_key in seen_chunks:
            continue
        seen_chunks.add(chunk_key)

        meta = None
        try:
            meta = storage.get_metadata(data_id, user_id=user_id or None)
        except Exception:
            pass

        source_name = (getattr(meta, "name", None) if meta else None) or data_id[:12]
        idx = len(numbered_sources) + 1
        numbered_sources.append({
            "index": idx,
            "data_id": data_id,
            "name": source_name,
            "chunk_text": chunk_text,
            "similarity": round(similarity, 4),
        })

    # 4. Build messages for the model
    if not numbered_sources:
        answer = "I don't have enough context in the stored data to answer that question. Try uploading relevant documents first."
        return ChatResponse(
            answer=answer,
            citations=[],
            model=None,
            latency_ms=int((time.monotonic() - t0) * 1000),
        )

    context_block = "\n\n".join(
        f"[{s['index']}] ({s['name']}) {s['chunk_text']}"
        for s in numbered_sources
    )

    system_prompt = (
        "You are a helpful assistant that answers questions based on the provided context. "
        "Use ONLY the information from the numbered sources below. "
        "Cite your sources using [N] notation inline (e.g. [1], [2]). "
        "If the context doesn't contain enough information to answer, say so. "
        "Format your response in markdown."
    )
    if entity_hints:
        system_prompt += (
            "\n\nKnown entities related to this query: "
            + ", ".join(entity_hints)
            + ". Use this context to improve your answer."
        )

    # Include last 10 turns of history
    history_messages = [
        {"role": m.role, "content": m.content}
        for m in request.history[-10:]
    ]

    messages = [
        {"role": "system", "content": system_prompt},
        *history_messages,
        {"role": "user", "content": f"Context:\n\n{context_block}\n\n---\n\nQuestion: {request.message}"},
    ]

    # 5. Get model response
    try:
        result = await _chat_completion(
            messages=messages,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            tier=request.model_tier,
        )
        answer = result["choices"][0]["message"]["content"].strip()
        used_model = result.get("model") or config.get_model_label(request.model_tier)
    except Exception as exc:
        logger.warning("Chat completion failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Model server error: {exc}")

    # 6. Record token usage for Insights dashboard
    usage = result.get("usage", {})
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)
    if total_tokens and user_id:
        try:
            from app.models import TokenUsageRecord
            storage.record_token_usage(TokenUsageRecord(
                user_id=user_id,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                model=used_model,
                agent_type="chat",
            ))
        except Exception as tok_err:
            logger.debug("Failed to record chat token usage: %s", tok_err)

    # 7. Extract cited source numbers and return only used citations
    cited_indices = {int(n) for n in re.findall(r"\[(\d+)\]", answer)}
    citations = [
        ChatCitation(**s)
        for s in numbered_sources
        if s["index"] in cited_indices
    ]

    latency_ms = int((time.monotonic() - t0) * 1000)
    logger.info("chat_with_data | sources=%d cited=%d tokens=%d latency_ms=%d", len(numbered_sources), len(citations), total_tokens, latency_ms)

    return ChatResponse(
        answer=answer,
        citations=citations,
        model=used_model,
        latency_ms=latency_ms,
    )


# ---------------------------------------------------------------------------
# Graphiti knowledge graph search helper
# ---------------------------------------------------------------------------


async def _graphiti_search(
    query: str, user_id: str, limit: int = 10,
    temporal: TemporalFilter | None = None,
) -> list[dict]:
    """Search Graphiti knowledge graph — returns results in dict format
    compatible with pgvector results for downstream merging.

    Raises HTTPException(400) if Neo4j is not configured.
    """
    from app.graphiti_client import is_graphiti_enabled, get_graphiti

    if not is_graphiti_enabled():
        raise HTTPException(
            status_code=400,
            detail="Graph search requires NEO4J_URI to be configured",
        )

    graphiti = await get_graphiti()

    try:
        from graphiti_core.search.search_config_recipes import EDGE_HYBRID_SEARCH_RRF
        search_config = EDGE_HYBRID_SEARCH_RRF.model_copy(deep=True)
        search_config.limit = limit

        kwargs: dict = {"query": query, "config": search_config}

        # Apply temporal filters if provided
        if temporal:
            from graphiti_core.search.search_config import SearchFilters, DateFilter, ComparisonOperator
            date_filters = []
            if temporal.valid_at:
                date_filters.append(
                    DateFilter(date=temporal.valid_at, comparison_operator=ComparisonOperator.less_than_or_equal)
                )
            if temporal.valid_after:
                date_filters.append(
                    DateFilter(date=temporal.valid_after, comparison_operator=ComparisonOperator.greater_than_or_equal)
                )
            if temporal.valid_before:
                date_filters.append(
                    DateFilter(date=temporal.valid_before, comparison_operator=ComparisonOperator.less_than_or_equal)
                )
            if date_filters:
                kwargs["filters"] = SearchFilters(valid_at=[date_filters])

        results = await graphiti.search(**kwargs)

        # Normalize Graphiti edges to mem-dog search result format
        normalized: list[dict] = []
        for edge in results:
            fact = getattr(edge, "fact", "") or str(edge)
            edge_uuid = getattr(edge, "uuid", "") or ""
            # Try to map back to mem-dog data_id via episode name
            episode_name = getattr(edge, "episode_name", None) or getattr(edge, "name", None) or ""

            normalized.append({
                "embedding_id": f"graphiti_{edge_uuid}",
                "data_id": episode_name,  # episode name = data_id (set in Phase 2)
                "chunk_text": fact,
                "similarity": 0.8,  # graph results don't have cosine similarity
                "fts_rank": None,
                "rrf_score": None,
                "search_type": "graph",
            })

        return normalized

    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Graphiti search failed: %s", exc)
        return []
