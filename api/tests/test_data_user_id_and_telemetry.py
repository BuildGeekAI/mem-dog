"""Tests for user_id tag and upload telemetry (data API plan)."""
import pytest
from unittest.mock import patch, MagicMock

from app import config

DEFAULT_UID = config.DEFAULT_USER_ID
DEFAULT_UID_TAG = f"user_id:{DEFAULT_UID}"


def test_create_data_adds_user_id_tag_when_not_present(client):
    """When tags omit user_id, create_data is called with a user_id:<owner> tag."""
    with patch("app.routers.data.get_storage") as mock_get_storage:
        mock_storage = MagicMock()
        mock_storage.create_data.return_value = ("data_01test", 1)
        mock_get_storage.return_value = mock_storage

        response = client.post("/api/v1/data", data={"content": "test"})

        assert response.status_code == 200
        mock_storage.create_data.assert_called_once()
        call_kwargs = mock_storage.create_data.call_args[1]
        tags = call_kwargs.get("tags") or []
        assert DEFAULT_UID_TAG in tags, f"expected {DEFAULT_UID_TAG} tag (default owner) in tags"


def test_create_data_adds_user_id_tag_for_given_owner(client):
    """When owner_user_id is provided, create_data is called with user_id:<that_owner>."""
    with patch("app.routers.data.get_storage") as mock_get_storage:
        mock_storage = MagicMock()
        mock_storage.create_data.return_value = ("data_01test", 1)
        mock_get_storage.return_value = mock_storage

        response = client.post(
            "/api/v1/data",
            data={"content": "test", "owner_user_id": "alice"},
        )

        assert response.status_code == 200
        call_kwargs = mock_storage.create_data.call_args[1]
        tags = call_kwargs.get("tags") or []
        assert "user_id:alice" in tags


def test_create_data_does_not_duplicate_user_id_tag(client):
    """When tags already include the default user_id tag, it is not duplicated."""
    with patch("app.routers.data.get_storage") as mock_get_storage:
        mock_storage = MagicMock()
        mock_storage.create_data.return_value = ("data_01test", 1)
        mock_get_storage.return_value = mock_storage

        response = client.post(
            "/api/v1/data",
            data={"content": "test", "tags": f"{DEFAULT_UID_TAG},work"},
        )

        assert response.status_code == 200
        call_kwargs = mock_storage.create_data.call_args[1]
        tags = call_kwargs.get("tags") or []
        assert tags.count(DEFAULT_UID_TAG) == 1
        assert "work" in tags
