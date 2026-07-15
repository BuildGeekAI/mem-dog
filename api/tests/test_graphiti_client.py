"""Tests for the Graphiti client module."""

import pytest

from app import config
from app.graphiti_client import (
    _build_graphiti_clients,
    _resolve_ollama_openai_base,
    is_graphiti_enabled,
)


class TestGraphitiEnabled:
    def test_disabled_by_default(self, monkeypatch):
        monkeypatch.delenv("NEO4J_URI", raising=False)
        assert is_graphiti_enabled() is False

    def test_enabled_when_uri_set(self, monkeypatch):
        monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
        assert is_graphiti_enabled() is True

    def test_empty_uri_is_disabled(self, monkeypatch):
        monkeypatch.setenv("NEO4J_URI", "")
        assert is_graphiti_enabled() is False


class TestOllamaOpenAiBase:
    def test_model_server_url_adds_v1_suffix(self, monkeypatch):
        monkeypatch.setattr(config, "MODEL_SERVER_URL", "http://host.docker.internal:11434")
        monkeypatch.setattr(config, "MODEL_SERVER_URL_MEDIUM", "")
        monkeypatch.setattr(config, "MODEL_SERVER_URL_SMALL", "")
        monkeypatch.setattr(config, "MODEL_SERVER_URL_LARGE", "")
        monkeypatch.setattr(
            config,
            "OLLAMA_LOCAL_API_BASE",
            "http://ollama.webhook-pipeline.svc.cluster.local:11434",
        )
        monkeypatch.setattr(config, "OLLAMA_TIER", False)
        assert _resolve_ollama_openai_base() == "http://host.docker.internal:11434/v1"

    def test_ollama_local_override_when_not_k8s_default(self, monkeypatch):
        monkeypatch.setattr(config, "MODEL_SERVER_URL", "")
        monkeypatch.setattr(config, "MODEL_SERVER_URL_MEDIUM", "")
        monkeypatch.setattr(config, "MODEL_SERVER_URL_SMALL", "")
        monkeypatch.setattr(config, "MODEL_SERVER_URL_LARGE", "")
        monkeypatch.setattr(config, "OLLAMA_LOCAL_API_BASE", "http://host.docker.internal:11434")
        monkeypatch.setattr(config, "OLLAMA_TIER", False)
        assert _resolve_ollama_openai_base() == "http://host.docker.internal:11434/v1"

    def test_returns_none_without_local_config(self, monkeypatch):
        monkeypatch.setattr(config, "MODEL_SERVER_URL", "")
        monkeypatch.setattr(config, "MODEL_SERVER_URL_MEDIUM", "")
        monkeypatch.setattr(config, "MODEL_SERVER_URL_SMALL", "")
        monkeypatch.setattr(config, "MODEL_SERVER_URL_LARGE", "")
        monkeypatch.setattr(
            config,
            "OLLAMA_LOCAL_API_BASE",
            "http://ollama.webhook-pipeline.svc.cluster.local:11434",
        )
        monkeypatch.setattr(config, "OLLAMA_TIER", False)
        assert _resolve_ollama_openai_base() is None


class TestBuildGraphitiClients:
    def test_raises_without_ai_provider(self, monkeypatch):
        monkeypatch.setattr(config, "SYSTEM_GEMINI_API_KEY", "")
        monkeypatch.setattr(config, "MODEL_SERVER_URL", "")
        monkeypatch.setattr(config, "MODEL_SERVER_URL_MEDIUM", "")
        monkeypatch.setattr(config, "MODEL_SERVER_URL_SMALL", "")
        monkeypatch.setattr(config, "MODEL_SERVER_URL_LARGE", "")
        monkeypatch.setattr(
            config,
            "OLLAMA_LOCAL_API_BASE",
            "http://ollama.webhook-pipeline.svc.cluster.local:11434",
        )
        monkeypatch.setattr(config, "OLLAMA_TIER", False)
        with pytest.raises(RuntimeError, match="Graphiti requires an AI provider"):
            _build_graphiti_clients()

    def test_prefers_gemini_over_local_ollama(self, monkeypatch):
        monkeypatch.setattr(config, "SYSTEM_GEMINI_API_KEY", "test-gemini-key")
        monkeypatch.setattr(config, "MODEL_SERVER_URL", "http://host.docker.internal:11434")
        llm_client, embedder, cross_encoder, provider = _build_graphiti_clients()
        assert provider == "gemini"
        assert llm_client is not None
        assert embedder is not None

    def test_uses_local_ollama_when_gemini_missing(self, monkeypatch):
        monkeypatch.setattr(config, "SYSTEM_GEMINI_API_KEY", "")
        monkeypatch.setattr(config, "MODEL_SERVER_URL", "http://host.docker.internal:11434")
        monkeypatch.setattr(config, "MODEL_SERVER_MODEL", "llama3.2:1b")
        monkeypatch.setattr(config, "OLLAMA_LOCAL_MODEL_EMBEDDING", "embeddinggemma")
        llm_client, embedder, cross_encoder, provider = _build_graphiti_clients()
        assert provider == "ollama_local"
        assert llm_client is not None
        assert embedder is not None
        assert cross_encoder is not None

    def test_ollama_requires_chat_and_embedding_models(self, monkeypatch):
        monkeypatch.setattr(config, "SYSTEM_GEMINI_API_KEY", "")
        monkeypatch.setattr(config, "MODEL_SERVER_URL", "http://host.docker.internal:11434")
        monkeypatch.setattr(config, "MODEL_SERVER_MODEL", "")
        monkeypatch.setattr(config, "OLLAMA_LOCAL_MODEL_EMBEDDING", "embeddinggemma")
        with pytest.raises(RuntimeError, match="MODEL_SERVER_MODEL"):
            _build_graphiti_clients()
