"""
Tests for chat endpoint with different model categories.
"""
import pytest
from unittest.mock import patch, AsyncMock


@pytest.fixture
def sample_chat_messages():
    """Sample chat messages for testing."""
    return [
        {"role": "user", "content": "Hello, how are you?"},
    ]


def test_chat_with_tier(client, sample_chat_messages):
    """Test chat endpoint with tier category."""
    with patch("app.routers.ai_query.httpx.AsyncClient") as mock_client:
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "I'm doing well!"}}],
            "usage": {"total_tokens": 10},
            "model": "test-model",
        }
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=mock_response
        )
        
        response = client.post(
            "/api/v1/ai/query/chat",
            json={
                "messages": sample_chat_messages,
                "category": "tier",
                "model_tier": "medium",
                "max_tokens": 512,
                "temperature": 0.7,
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert data["category"] == "tier"
        assert data["model_tier"] == "medium"


def test_chat_invalid_category(client, sample_chat_messages):
    """Test chat endpoint with invalid category."""
    response = client.post(
        "/api/v1/ai/query/chat",
        json={
            "messages": sample_chat_messages,
            "category": "invalid-category",
            "max_tokens": 512,
            "temperature": 0.7,
        },
    )
    assert response.status_code == 422


