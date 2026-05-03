"""Reranking utilities for multi-signal search fusion.

Pure functions — no storage or framework dependencies.
"""

import math
from typing import Any

import httpx


def rrf_merge(*ranked_lists: list[dict], k: int = 60, weights: list[float] | None = None) -> list[dict]:
    """Reciprocal Rank Fusion — merge N ranked lists into one.

    Each item in a ranked list must have a unique key accessible via
    ``item["embedding_id"]`` (or ``item["id"]``).  The merged list is
    sorted by descending RRF score.

    Args:
        *ranked_lists: One or more lists of result dicts, each pre-sorted
            by relevance (best first).
        k: RRF constant (default 60).  Higher values flatten rank differences.
        weights: Optional per-list weight multipliers (default: equal weight).
    """
    if not ranked_lists:
        return []

    if weights is None:
        weights = [1.0] * len(ranked_lists)
    elif len(weights) != len(ranked_lists):
        weights = [1.0] * len(ranked_lists)

    scores: dict[str, float] = {}
    items: dict[str, dict] = {}

    for idx, rlist in enumerate(ranked_lists):
        w = weights[idx]
        for rank, item in enumerate(rlist):
            key = item.get("embedding_id") or item.get("id") or str(id(item))
            scores[key] = scores.get(key, 0.0) + w / (k + rank + 1)
            if key not in items:
                items[key] = item

    merged = sorted(items.values(), key=lambda x: scores.get(
        x.get("embedding_id") or x.get("id") or str(id(x)), 0.0
    ), reverse=True)

    # Attach rrf_score to each item
    for item in merged:
        key = item.get("embedding_id") or item.get("id") or str(id(item))
        item["rrf_score"] = round(scores.get(key, 0.0), 6)

    return merged


def mmr_rerank(
    results: list[dict],
    query_vector: list[float],
    lambda_param: float = 0.5,
    top_k: int = 5,
) -> list[dict]:
    """Maximal Marginal Relevance — balance relevance vs diversity.

    Each result dict should have a ``"vector"`` key with its embedding.
    If vectors are missing, returns results unchanged (truncated to top_k).

    Args:
        results: List of result dicts with optional ``"vector"`` field.
        query_vector: The query embedding.
        lambda_param: Trade-off between relevance (1.0) and diversity (0.0).
        top_k: Number of results to return.
    """
    if not results or not query_vector:
        return results[:top_k]

    # Filter to results that have vectors for MMR; keep others as fallback
    with_vec = [r for r in results if r.get("vector")]
    without_vec = [r for r in results if not r.get("vector")]

    if not with_vec:
        return results[:top_k]

    selected: list[dict] = []
    candidates = list(with_vec)

    for _ in range(min(top_k, len(candidates))):
        best_score = -float("inf")
        best_idx = 0

        for i, cand in enumerate(candidates):
            relevance = _cosine_sim(query_vector, cand["vector"])

            max_sim_to_selected = 0.0
            for sel in selected:
                sim = _cosine_sim(cand["vector"], sel["vector"])
                max_sim_to_selected = max(max_sim_to_selected, sim)

            mmr_score = lambda_param * relevance - (1 - lambda_param) * max_sim_to_selected
            if mmr_score > best_score:
                best_score = mmr_score
                best_idx = i

        selected.append(candidates.pop(best_idx))

    # Fill remaining slots with non-vector results
    remaining = top_k - len(selected)
    if remaining > 0:
        selected.extend(without_vec[:remaining])

    return selected


def node_distance_rerank(
    results: list[dict],
    entity_distances: dict[str, int],
    decay: float = 0.5,
) -> list[dict]:
    """Boost results closer to query entities in the graph.

    Args:
        results: List of result dicts with ``"data_id"`` field.
        entity_distances: Mapping of data_id → BFS hop distance from query entity.
        decay: Exponential decay factor per hop.
    """
    if not entity_distances:
        return results

    for r in results:
        data_id = r.get("data_id", "")
        dist = entity_distances.get(data_id)
        if dist is not None:
            boost = decay ** dist
            base = r.get("similarity", 0.0) or r.get("rrf_score", 0.0) or 0.5
            r["similarity"] = round(base + boost * (1 - base), 4)

    results.sort(key=lambda x: x.get("similarity", 0.0), reverse=True)
    return results


def episode_mentions_rerank(
    results: list[dict],
    mention_counts: dict[str, int],
    boost: float = 0.1,
) -> list[dict]:
    """Boost results mentioned by more graph entities/episodes.

    Args:
        results: List of result dicts with ``"data_id"`` field.
        mention_counts: Mapping of data_id → number of entity mentions.
        boost: Score boost per mention.
    """
    if not mention_counts:
        return results

    for r in results:
        data_id = r.get("data_id", "")
        count = mention_counts.get(data_id, 0)
        if count > 0:
            base = r.get("similarity", 0.0) or r.get("rrf_score", 0.0) or 0.5
            r["similarity"] = round(min(base + boost * count, 1.0), 4)

    results.sort(key=lambda x: x.get("similarity", 0.0), reverse=True)
    return results


async def cross_encoder_rerank(
    query: str,
    candidates: list[dict],
    model_url: str,
    top_k: int = 5,
) -> list[dict]:
    """LLM-based relevance scoring via model server.

    Sends (query, chunk_text) pairs to the model server's rerank endpoint.
    Falls back to returning candidates unchanged if the server is unavailable.

    Args:
        query: The search query.
        candidates: List of result dicts with ``"chunk_text"`` field.
        model_url: Base URL of the model server (e.g. Ollama).
        top_k: Number of results to return.
    """
    if not candidates:
        return []

    pairs = [
        {"query": query, "text": c.get("chunk_text", "")}
        for c in candidates
    ]

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{model_url}/v1/rerank",
                json={"pairs": pairs, "top_k": top_k},
            )
            resp.raise_for_status()
            data = resp.json()

        # Expect response like {"results": [{"index": 0, "score": 0.95}, ...]}
        scored = data.get("results", [])
        scored.sort(key=lambda x: x.get("score", 0.0), reverse=True)

        reranked = []
        for s in scored[:top_k]:
            idx = s.get("index", 0)
            if 0 <= idx < len(candidates):
                item = candidates[idx].copy()
                item["cross_encoder_score"] = round(s.get("score", 0.0), 4)
                reranked.append(item)
        return reranked

    except Exception:
        # Fallback: return candidates as-is
        return candidates[:top_k]


def _cosine_sim(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)
