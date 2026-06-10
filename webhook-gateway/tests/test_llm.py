"""Unit tests for the multi-provider LLM client."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.llm import classify_message, get_provider_info, summarize_context


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FakeResponse:
    def __init__(self, text: str):
        self.text = text


class _FakeModels:
    def __init__(self, text: str):
        self._text = text

    def generate_content(self, **kwargs):
        return _FakeResponse(self._text)


class _FakeGeminiClient:
    def __init__(self, text: str):
        self.models = _FakeModels(text)


def _mock_gemini_config(cfg, *, provider: str = "gemini", api_key: str = "key", model: str = "gemini-3.0-flash"):
    """Configure mock config for native Gemini path."""
    cfg.LLM_PROVIDER = provider
    cfg.GEMINI_API_KEY = api_key
    cfg.GEMINI_MODEL = model
    cfg.LLM_MODEL = ""
    cfg.LLM_API_KEY = ""
    cfg.LLM_API_BASE = ""
    cfg.has_llm_configured = lambda: bool(api_key)
    cfg.get_effective_model = lambda: model


def _mock_litellm_config(cfg, *, provider: str = "openai", model: str = "openai/gpt-4o"):
    """Configure mock config for the litellm path."""
    cfg.LLM_PROVIDER = provider
    cfg.GEMINI_API_KEY = ""
    cfg.GEMINI_MODEL = "gemini-3.0-flash"
    cfg.LLM_MODEL = model
    cfg.LLM_API_KEY = "test-key"
    cfg.LLM_API_BASE = ""
    cfg.has_llm_configured = lambda: True
    cfg.get_effective_model = lambda: model


# ---------------------------------------------------------------------------
# classify_message — native Gemini path
# ---------------------------------------------------------------------------

class TestClassifyMessageGemini:
    @pytest.mark.asyncio
    async def test_returns_parsed_json(self):
        fake = _FakeGeminiClient('{"intent": "action_required", "category": "task", "confidence": 0.95}')
        with patch("app.llm._get_gemini_client", return_value=fake), \
             patch("app.llm.config") as cfg:
            _mock_gemini_config(cfg)
            result = await classify_message("Please review the PR")
        assert result["intent"] == "action_required"
        assert result["confidence"] == 0.95

    @pytest.mark.asyncio
    async def test_handles_markdown_wrapped_json(self):
        fake = _FakeGeminiClient('```json\n{"intent": "informational", "category": "info", "confidence": 0.8}\n```')
        with patch("app.llm._get_gemini_client", return_value=fake), \
             patch("app.llm.config") as cfg:
            _mock_gemini_config(cfg)
            result = await classify_message("FYI the build passed")
        assert result["intent"] == "informational"

    @pytest.mark.asyncio
    async def test_no_api_key(self):
        with patch("app.llm.config") as cfg:
            _mock_gemini_config(cfg, api_key="")
            result = await classify_message("test")
        assert result["intent"] == "unknown"

    @pytest.mark.asyncio
    async def test_empty_text(self):
        with patch("app.llm.config") as cfg:
            _mock_gemini_config(cfg)
            result = await classify_message("")
        assert result["intent"] == "unknown"

    @pytest.mark.asyncio
    async def test_api_error_returns_fallback(self):
        class _BrokenModels:
            def generate_content(self, **kwargs):
                raise RuntimeError("boom")
        class _BrokenClient:
            models = _BrokenModels()
        with patch("app.llm._get_gemini_client", return_value=_BrokenClient()), \
             patch("app.llm.config") as cfg:
            _mock_gemini_config(cfg)
            result = await classify_message("test")
        assert result["intent"] == "unknown"


# ---------------------------------------------------------------------------
# summarize_context — native Gemini path
# ---------------------------------------------------------------------------

class TestSummarizeContextGemini:
    @pytest.mark.asyncio
    async def test_returns_summary(self):
        fake = _FakeGeminiClient("The meeting discussed project timelines.")
        with patch("app.llm._get_gemini_client", return_value=fake), \
             patch("app.llm.config") as cfg:
            _mock_gemini_config(cfg)
            result = await summarize_context("Long meeting transcript...")
        assert "meeting" in result.lower()

    @pytest.mark.asyncio
    async def test_no_api_key(self):
        with patch("app.llm.config") as cfg:
            _mock_gemini_config(cfg, api_key="")
            result = await summarize_context("test")
        assert result == ""

    @pytest.mark.asyncio
    async def test_api_error_returns_empty(self):
        class _BrokenModels:
            def generate_content(self, **kwargs):
                raise RuntimeError("boom")
        class _BrokenClient:
            models = _BrokenModels()
        with patch("app.llm._get_gemini_client", return_value=_BrokenClient()), \
             patch("app.llm.config") as cfg:
            _mock_gemini_config(cfg)
            result = await summarize_context("test")
        assert result == ""


# ---------------------------------------------------------------------------
# classify_message — litellm path
# ---------------------------------------------------------------------------

class TestClassifyMessageLitellm:
    @pytest.mark.asyncio
    async def test_routes_through_litellm(self):
        fake_choice = MagicMock()
        fake_choice.message.content = '{"intent": "action_required", "category": "task", "confidence": 0.9}'
        fake_response = MagicMock()
        fake_response.choices = [fake_choice]

        with patch("app.llm.config") as cfg, \
             patch("litellm.acompletion", new_callable=AsyncMock, return_value=fake_response) as mock_ac:
            _mock_litellm_config(cfg, provider="openai", model="openai/gpt-4o")
            result = await classify_message("Urgent: deploy fix")

        assert result["intent"] == "action_required"
        mock_ac.assert_awaited_once()
        call_kwargs = mock_ac.call_args.kwargs
        assert call_kwargs["model"] == "openai/gpt-4o"

    @pytest.mark.asyncio
    async def test_litellm_error_returns_fallback(self):
        with patch("app.llm.config") as cfg, \
             patch("litellm.acompletion", new_callable=AsyncMock, side_effect=RuntimeError("API down")):
            _mock_litellm_config(cfg, provider="anthropic", model="anthropic/claude-sonnet-4-6-20250514")
            result = await classify_message("test")
        assert result["intent"] == "unknown"

    @pytest.mark.asyncio
    async def test_litellm_uses_api_key_and_base(self):
        fake_choice = MagicMock()
        fake_choice.message.content = '{"intent": "unknown", "category": "x", "confidence": 0.5}'
        fake_response = MagicMock()
        fake_response.choices = [fake_choice]

        with patch("app.llm.config") as cfg, \
             patch("litellm.acompletion", new_callable=AsyncMock, return_value=fake_response) as mock_ac:
            _mock_litellm_config(cfg, provider="ollama", model="ollama/llama3")
            cfg.LLM_API_KEY = "custom-key"
            cfg.LLM_API_BASE = "http://localhost:11434"
            await classify_message("hello")

        call_kwargs = mock_ac.call_args.kwargs
        assert call_kwargs["api_key"] == "custom-key"
        assert call_kwargs["api_base"] == "http://localhost:11434"


# ---------------------------------------------------------------------------
# summarize_context — litellm path
# ---------------------------------------------------------------------------

class TestSummarizeContextLitellm:
    @pytest.mark.asyncio
    async def test_routes_through_litellm(self):
        fake_choice = MagicMock()
        fake_choice.message.content = "The discussion covered quarterly revenue."
        fake_response = MagicMock()
        fake_response.choices = [fake_choice]

        with patch("app.llm.config") as cfg, \
             patch("litellm.acompletion", new_callable=AsyncMock, return_value=fake_response):
            _mock_litellm_config(cfg, provider="mistral", model="mistral/mistral-large-latest")
            result = await summarize_context("Long transcript...")
        assert "revenue" in result.lower()


# ---------------------------------------------------------------------------
# get_provider_info
# ---------------------------------------------------------------------------

class TestGetProviderInfo:
    def test_gemini_defaults(self):
        with patch("app.llm.config") as cfg:
            _mock_gemini_config(cfg)
            info = get_provider_info()
        assert info["provider"] == "gemini"
        assert info["configured"] is True

    def test_openai_provider(self):
        with patch("app.llm.config") as cfg:
            _mock_litellm_config(cfg, provider="openai")
            info = get_provider_info()
        assert info["provider"] == "openai"
        assert info["configured"] is True

    def test_unconfigured(self):
        with patch("app.llm.config") as cfg:
            _mock_gemini_config(cfg, api_key="")
            info = get_provider_info()
        assert info["configured"] is False
