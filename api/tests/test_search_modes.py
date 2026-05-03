"""Tests for search mode models and backward compatibility."""

import pytest
from app.routers.ai_query import (
    SearchMode, RerankMethod, RerankConfig, TemporalFilter,
    SemanticQueryRequest, SemanticMatchChunk, ChatRequest,
)


class TestSearchModeEnum:
    def test_all_modes(self):
        assert SearchMode.vector == "vector"
        assert SearchMode.fts == "fts"
        assert SearchMode.hybrid == "hybrid"
        assert SearchMode.graph == "graph"
        assert SearchMode.full == "full"

    def test_default_is_vector(self):
        req = SemanticQueryRequest(query="test")
        assert req.search_mode == SearchMode.vector

    def test_backward_compat(self):
        """Existing clients that don't send search_mode get vector mode."""
        req = SemanticQueryRequest(query="test", max_results=3)
        assert req.search_mode == SearchMode.vector
        assert req.rerank.method == RerankMethod.none


class TestRerankConfig:
    def test_defaults(self):
        cfg = RerankConfig()
        assert cfg.method == RerankMethod.none
        assert cfg.mmr_lambda == 0.5
        assert cfg.cross_encoder_tier == "small"

    def test_mmr_config(self):
        cfg = RerankConfig(method=RerankMethod.mmr, mmr_lambda=0.7)
        assert cfg.method == RerankMethod.mmr
        assert cfg.mmr_lambda == 0.7


class TestTemporalFilter:
    def test_empty(self):
        tf = TemporalFilter()
        assert tf.valid_at is None
        assert tf.valid_after is None
        assert tf.valid_before is None

    def test_with_datetime(self):
        from datetime import datetime, timezone
        dt = datetime(2025, 6, 1, tzinfo=timezone.utc)
        tf = TemporalFilter(valid_at=dt)
        assert tf.valid_at == dt


class TestSemanticMatchChunk:
    def test_new_fields_optional(self):
        chunk = SemanticMatchChunk(
            embedding_id="emb_1",
            chunk_text="hello world",
            similarity=0.95,
        )
        assert chunk.fts_rank is None
        assert chunk.rrf_score is None
        assert chunk.search_type is None

    def test_with_new_fields(self):
        chunk = SemanticMatchChunk(
            embedding_id="emb_1",
            chunk_text="hello world",
            similarity=0.95,
            fts_rank=0.8,
            rrf_score=0.012,
            search_type="both",
        )
        assert chunk.fts_rank == 0.8
        assert chunk.search_type == "both"


class TestChatRequest:
    def test_default_search_mode(self):
        req = ChatRequest(message="hello")
        assert req.search_mode == SearchMode.vector
        assert req.rerank.method == RerankMethod.none
        assert req.temporal is None

    def test_with_search_mode(self):
        req = ChatRequest(
            message="hello",
            search_mode=SearchMode.hybrid,
            vector_weight=0.7,
            fts_weight=0.3,
        )
        assert req.search_mode == SearchMode.hybrid
        assert req.vector_weight == 0.7
