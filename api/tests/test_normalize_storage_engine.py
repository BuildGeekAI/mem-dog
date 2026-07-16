"""Tests for AI engine normalization before AISignature persistence."""

from app.storage import _normalize_storage_engine


def test_valid_engines_pass_through():
    assert _normalize_storage_engine("gemini") == "gemini"
    assert _normalize_storage_engine("ollama") == "ollama"
    assert _normalize_storage_engine("openai") == "openai"


def test_aliases_map_to_valid_engine():
    assert _normalize_storage_engine("google") == "gemini"
    assert _normalize_storage_engine("vertex_ai") == "gemini"
    assert _normalize_storage_engine("local") == "ollama"
    assert _normalize_storage_engine("model_server") == "ollama"
    assert _normalize_storage_engine("ollama_local") == "ollama"


def test_litellm_provider_prefix_normalized():
    assert _normalize_storage_engine("google/gemini-2.0-flash") == "gemini"
    assert _normalize_storage_engine("ollama/gemma3:12b") == "ollama"


def test_bare_model_names_default_to_ollama():
    assert _normalize_storage_engine("llama3.2:1b") == "ollama"
    assert _normalize_storage_engine("gemma3:12b") == "ollama"


def test_empty_defaults_to_ollama():
    assert _normalize_storage_engine("") == "ollama"
