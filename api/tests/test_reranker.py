"""Tests for the reranker module (RRF, MMR, node_distance, episode_mentions)."""

import pytest
from app.reranker import rrf_merge, mmr_rerank, node_distance_rerank, episode_mentions_rerank


class TestRRFMerge:
    def test_empty_input(self):
        assert rrf_merge() == []

    def test_single_list(self):
        items = [
            {"embedding_id": "a", "data_id": "d1", "chunk_text": "hello"},
            {"embedding_id": "b", "data_id": "d2", "chunk_text": "world"},
        ]
        result = rrf_merge(items)
        assert len(result) == 2
        assert result[0]["embedding_id"] == "a"
        assert "rrf_score" in result[0]

    def test_two_lists_merge(self):
        list1 = [
            {"embedding_id": "a", "data_id": "d1", "chunk_text": "hello"},
            {"embedding_id": "b", "data_id": "d2", "chunk_text": "world"},
        ]
        list2 = [
            {"embedding_id": "b", "data_id": "d2", "chunk_text": "world"},
            {"embedding_id": "c", "data_id": "d3", "chunk_text": "foo"},
        ]
        result = rrf_merge(list1, list2)
        assert len(result) == 3
        # "b" appears in both lists, should be ranked higher
        ids = [r["embedding_id"] for r in result]
        assert ids[0] == "b"

    def test_weighted_merge(self):
        list1 = [{"embedding_id": "a", "data_id": "d1", "chunk_text": "x"}]
        list2 = [{"embedding_id": "b", "data_id": "d2", "chunk_text": "y"}]
        result = rrf_merge(list1, list2, weights=[10.0, 1.0])
        assert result[0]["embedding_id"] == "a"

    def test_k_parameter(self):
        """Higher k flattens rank differences, reducing the score for top-ranked items."""
        import copy
        items_low = [
            {"embedding_id": "a", "data_id": "d1", "chunk_text": "x"},
            {"embedding_id": "b", "data_id": "d2", "chunk_text": "y"},
        ]
        items_high = copy.deepcopy(items_low)
        result_low_k = rrf_merge(items_low, k=1)
        result_high_k = rrf_merge(items_high, k=1000)
        # With low k, rank 0 gets 1/(1+0+1) = 0.5; with high k, 1/(1000+0+1) ≈ 0.001
        assert result_low_k[0]["rrf_score"] > result_high_k[0]["rrf_score"]


class TestMMRRerank:
    def test_empty_input(self):
        assert mmr_rerank([], [1.0, 0.0], top_k=5) == []

    def test_no_vectors_returns_truncated(self):
        results = [
            {"embedding_id": "a", "chunk_text": "hello"},
            {"embedding_id": "b", "chunk_text": "world"},
            {"embedding_id": "c", "chunk_text": "foo"},
        ]
        result = mmr_rerank(results, [1.0, 0.0], top_k=2)
        assert len(result) == 2

    def test_with_vectors(self):
        results = [
            {"embedding_id": "a", "chunk_text": "hello", "vector": [1.0, 0.0]},
            {"embedding_id": "b", "chunk_text": "world", "vector": [0.9, 0.1]},
            {"embedding_id": "c", "chunk_text": "foo", "vector": [0.0, 1.0]},
        ]
        query_vec = [1.0, 0.0]
        result = mmr_rerank(results, query_vec, lambda_param=0.5, top_k=3)
        assert len(result) == 3
        # First result should be most relevant to query
        assert result[0]["embedding_id"] == "a"

    def test_high_diversity(self):
        results = [
            {"embedding_id": "a", "chunk_text": "hello", "vector": [1.0, 0.0]},
            {"embedding_id": "b", "chunk_text": "world", "vector": [0.99, 0.01]},
            {"embedding_id": "c", "chunk_text": "foo", "vector": [0.0, 1.0]},
        ]
        # Lambda=0 means maximum diversity
        result = mmr_rerank(results, [1.0, 0.0], lambda_param=0.0, top_k=2)
        ids = {r["embedding_id"] for r in result}
        # Should pick diverse items
        assert "c" in ids


class TestNodeDistanceRerank:
    def test_empty_distances(self):
        results = [{"data_id": "d1", "similarity": 0.5}]
        result = node_distance_rerank(results, {})
        assert result[0]["similarity"] == 0.5

    def test_boost_close_nodes(self):
        results = [
            {"data_id": "d1", "similarity": 0.3},
            {"data_id": "d2", "similarity": 0.5},
        ]
        # d1 is 1 hop away, d2 is 3 hops away
        entity_distances = {"d1": 1, "d2": 3}
        result = node_distance_rerank(results, entity_distances, decay=0.5)
        # d1 should be boosted more (closer)
        assert result[0]["data_id"] == "d1"


class TestEpisodeMentionsRerank:
    def test_empty_mentions(self):
        results = [{"data_id": "d1", "similarity": 0.5}]
        result = episode_mentions_rerank(results, {})
        assert result[0]["similarity"] == 0.5

    def test_boost_mentioned(self):
        results = [
            {"data_id": "d1", "similarity": 0.5},
            {"data_id": "d2", "similarity": 0.5},
        ]
        mention_counts = {"d1": 5, "d2": 1}
        result = episode_mentions_rerank(results, mention_counts, boost=0.1)
        assert result[0]["data_id"] == "d1"
        assert result[0]["similarity"] > result[1]["similarity"]

    def test_capped_at_1(self):
        results = [{"data_id": "d1", "similarity": 0.9}]
        result = episode_mentions_rerank(results, {"d1": 100}, boost=0.1)
        assert result[0]["similarity"] <= 1.0
