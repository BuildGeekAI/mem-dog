"""Unit tests for webhook_events.dispatch_upload_event.

Canonical payload format: { "data": { "url": ..., "payload": {...} }, "meta_data": {...} }
"""
import pytest
from unittest.mock import MagicMock, patch


def test_dispatch_upload_event_posts_canonical_payload():
    """dispatch_upload_event POSTs canonical {data, meta_data} payload with correct headers."""
    storage = MagicMock()
    storage.get_metadata.return_value = MagicMock(
        memory_ids=["timeline-demo", "mem_session_abc123"]
    )

    with patch("app.webhook_events.config") as mock_config:
        mock_config.WEBHOOK_GATEWAY_URL = "https://webhook.example.com/webhook"
        mock_config.WEBHOOK_API_KEY = "test-api-key"

        with patch("app.webhook_events.httpx.Client") as mock_client_cls:
            mock_resp = MagicMock()
            mock_resp.status_code = 202
            mock_client = MagicMock()
            mock_client.__enter__.return_value.post.return_value = mock_resp
            mock_client_cls.return_value = mock_client

            from app.webhook_events import dispatch_upload_event

            dispatch_upload_event(
                storage=storage,
                data_id="data_01ABC",
                base_url="https://api.example.com",
                content_type="image/png",
                user_id="demo",
                name="photo.png",
                description="A photo",
                tags=["image", "photo"],
                memory_ids=["mem_session_xyz"],
            )

            mock_client.__enter__.return_value.post.assert_called_once()
            call_kwargs = mock_client.__enter__.return_value.post.call_args[1]
            assert call_kwargs["headers"]["x-api-key"] == "test-api-key"
            assert call_kwargs["headers"]["Content-Type"] == "application/json"

            payload = call_kwargs["json"]
            assert set(payload.keys()) == {"data", "meta_data"}, "payload must have only data and meta_data"
            assert payload["data"]["url"] == "https://api.example.com/api/v1/data/data_01ABC"
            assert payload["data"]["payload"]["event"] == "data.uploaded"
            assert payload["data"]["payload"]["data_url"] == "https://api.example.com/api/v1/data/data_01ABC"
            assert payload["data"]["payload"]["data_id"] == "data_01ABC"
            assert payload["data"]["payload"]["name"] == "photo.png"
            assert payload["data"]["payload"]["description"] == "A photo"
            assert payload["data"]["payload"]["tags"] == ["image", "photo"]

            # Nested meta_data structure
            assert payload["meta_data"]["identity"]["user_id"] == "demo"
            assert payload["meta_data"]["content"]["mime_type"] == "image/png"
            assert payload["meta_data"]["access"]["data_id"] == "data_01ABC"
            assert payload["meta_data"]["access"]["is_downloaded"] is True
            # Removed fields should not be in meta_data
            assert "user_name" not in payload["meta_data"]
            assert "mimetype" not in payload["meta_data"]
            assert "name" not in payload["meta_data"]
            assert "description" not in payload["meta_data"]
            assert "tags" not in payload["meta_data"]


def test_dispatch_upload_event_includes_url_and_is_downloaded_in_meta_data():
    """meta_data includes data_id, url, is_downloaded so receiver/processor/agent preserve them."""
    storage = MagicMock()
    storage.get_user.return_value = None
    storage.get_metadata.return_value = None

    with patch("app.webhook_events.config") as mock_config:
        mock_config.WEBHOOK_GATEWAY_URL = "https://webhook.example.com/webhook"
        mock_config.WEBHOOK_API_KEY = "key"
        with patch("app.webhook_events.httpx.Client") as mock_client_cls:
            mock_resp = MagicMock()
            mock_resp.status_code = 202
            mock_client = MagicMock()
            mock_client.__enter__.return_value.post.return_value = mock_resp
            mock_client_cls.return_value = mock_client

            from app.webhook_events import dispatch_upload_event

            dispatch_upload_event(
                storage=storage,
                data_id="data_xyz",
                base_url="https://api.example.com",
                content_type="application/pdf",
                user_id="alice",
                url="https://example.com/doc.pdf",
                is_downloaded=True,
            )

            call_kwargs = mock_client.__enter__.return_value.post.call_args[1]
            payload = call_kwargs["json"]
            assert payload["meta_data"]["access"]["data_id"] == "data_xyz"
            assert payload["meta_data"]["access"]["url"] == "https://example.com/doc.pdf"
            assert payload["meta_data"]["access"]["is_downloaded"] is True


def test_dispatch_upload_event_skips_when_webhook_not_configured():
    """dispatch_upload_event does nothing when WEBHOOK_GATEWAY_URL or WEBHOOK_API_KEY is empty."""
    storage = MagicMock()

    with patch("app.webhook_events.config") as mock_config:
        mock_config.WEBHOOK_GATEWAY_URL = ""
        mock_config.WEBHOOK_API_KEY = "key"

        with patch("app.webhook_events.httpx.Client") as mock_client_cls:
            from app.webhook_events import dispatch_upload_event

            dispatch_upload_event(
                storage=storage,
                data_id="data_01",
                base_url="https://api.example.com",
                content_type="application/json",
                user_id="demo",
            )

            mock_client_cls.assert_not_called()
