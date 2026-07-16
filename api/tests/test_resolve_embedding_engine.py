"""Lean embedding resolution: cloud keys beat forced host Ollama when OLLAMA_TIER=false."""

from unittest.mock import MagicMock

from app import config
from app.storage import BaseStorage


def _resolve(monkeypatch, **overrides):
    defaults = {
        "OLLAMA_LOCAL_API_BASE": "",
        "OLLAMA_TIER": False,
        "OLLAMA_CLOUD_API_KEY": "",
        "SYSTEM_GEMINI_API_KEY": "",
        "OLLAMA_LOCAL_MODEL_EMBEDDING": "embeddinggemma",
        "OLLAMA_CLOUD_MODEL_EMBEDDING": "embeddinggemma",
        "SYSTEM_GEMINI_MODEL_EMBEDDING": "text-embedding-004",
    }
    defaults.update(overrides)
    for key, value in defaults.items():
        monkeypatch.setattr(config, key, value)
    return BaseStorage._resolve_embedding_engine(MagicMock(), None)


class TestResolveEmbeddingEngineLean:
    def test_host_ollama_when_no_cloud_key(self, monkeypatch):
        engine, model, key = _resolve(
            monkeypatch,
            OLLAMA_LOCAL_API_BASE="http://host.docker.internal:11434",
            OLLAMA_TIER=False,
        )
        assert engine == "ollama_local"
        assert model == "embeddinggemma"
        assert key == ""

    def test_cloud_beats_forced_host_url(self, monkeypatch):
        engine, model, key = _resolve(
            monkeypatch,
            OLLAMA_LOCAL_API_BASE="http://host.docker.internal:11434",
            OLLAMA_TIER=False,
            OLLAMA_CLOUD_API_KEY="cloud-key",
        )
        assert engine == "ollama_cloud"
        assert key == "cloud-key"

    def test_gemini_beats_forced_host_url(self, monkeypatch):
        engine, model, key = _resolve(
            monkeypatch,
            OLLAMA_LOCAL_API_BASE="http://host.docker.internal:11434",
            OLLAMA_TIER=False,
            SYSTEM_GEMINI_API_KEY="gem-key",
        )
        assert engine == "gemini"
        assert key == "gem-key"

    def test_skips_k8s_default_when_tier_off(self, monkeypatch):
        engine, model, key = _resolve(
            monkeypatch,
            OLLAMA_LOCAL_API_BASE=(
                "http://ollama.webhook-pipeline.svc.cluster.local:11434"
            ),
            OLLAMA_TIER=False,
            OLLAMA_CLOUD_API_KEY="cloud-key",
        )
        assert engine == "ollama_cloud"

    def test_tier_on_prefers_local_even_with_cloud(self, monkeypatch):
        engine, model, key = _resolve(
            monkeypatch,
            OLLAMA_LOCAL_API_BASE=(
                "http://ollama.webhook-pipeline.svc.cluster.local:11434"
            ),
            OLLAMA_TIER=True,
            OLLAMA_CLOUD_API_KEY="cloud-key",
        )
        assert engine == "ollama_local"
