"""Tests for forward_to_webhook flag on create_data endpoint."""
import pytest
from unittest.mock import patch, MagicMock


def test_create_data_without_forward_to_webhook_does_not_dispatch(client):
    """When forward_to_webhook is omitted or false, dispatch_upload_event is not called."""
    with patch("app.routers.data.webhook_events.dispatch_upload_event") as mock_dispatch:
        with patch("app.routers.data.get_storage") as mock_get_storage:
            mock_storage = MagicMock()
            mock_storage.create_data.return_value = ("data_01test", 1)
            mock_get_storage.return_value = mock_storage

            response = client.post("/api/v1/data", data={"content": "test"})

            assert response.status_code == 200
            mock_dispatch.assert_not_called()


def test_create_data_with_forward_to_webhook_false_does_not_dispatch(client):
    """When forward_to_webhook is false, dispatch_upload_event is not called."""
    with patch("app.routers.data.webhook_events.dispatch_upload_event") as mock_dispatch:
        with patch("app.routers.data.get_storage") as mock_get_storage:
            mock_storage = MagicMock()
            mock_storage.create_data.return_value = ("data_01test", 1)
            mock_get_storage.return_value = mock_storage

            response = client.post(
                "/api/v1/data",
                data={"content": "test", "forward_to_webhook": "false"},
            )

            assert response.status_code == 200
            mock_dispatch.assert_not_called()
