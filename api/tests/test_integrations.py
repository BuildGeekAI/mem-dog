"""Tests for the integration platform router.

These tests validate provider CRUD, connection lifecycle, and OAuth state
management. They use the FastAPI test client and mock Supabase interactions.
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    """Create a test client with mocked Supabase."""
    from main import app
    return TestClient(app)


def _mock_supabase_table(data=None, side_effect=None):
    """Build a mock chain for Supabase table().select().eq()...execute()."""
    mock_result = MagicMock()
    mock_result.data = data or []

    mock_chain = MagicMock()
    # Make all chaining methods return the same chain
    for method in ("select", "eq", "like", "order", "limit", "insert", "upsert", "update", "delete"):
        getattr(mock_chain, method).return_value = mock_chain
    mock_chain.execute.return_value = mock_result
    if side_effect:
        mock_chain.execute.side_effect = side_effect

    return mock_chain


# ---------------------------------------------------------------------------
# Provider Tests
# ---------------------------------------------------------------------------

class TestProviders:

    @patch("app.routers.integrations._get_supabase_client")
    def test_list_providers_empty(self, mock_get_client, client):
        mock_client = MagicMock()
        mock_client.table.return_value = _mock_supabase_table(data=[])
        mock_get_client.return_value = mock_client

        resp = client.get("/api/v1/integrations/providers")
        assert resp.status_code == 200
        assert resp.json() == []

    @patch("app.routers.integrations._get_supabase_client")
    def test_list_providers_with_data(self, mock_get_client, client):
        providers = [
            {
                "provider_key": "slack",
                "display_name": "Slack",
                "description": "Team messaging",
                "logo_url": "",
                "category": "communication",
                "auth_mode": "OAUTH2",
                "authorization_url": "https://slack.com/oauth/v2/authorize",
                "token_url": "https://slack.com/api/oauth.v2.access",
                "scope": "channels:read",
                "proxy_base_url": "https://slack.com/api",
                "config": {},
                "is_enabled": True,
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z",
            }
        ]
        mock_client = MagicMock()
        mock_client.table.return_value = _mock_supabase_table(data=providers)
        mock_get_client.return_value = mock_client

        resp = client.get("/api/v1/integrations/providers")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["provider_key"] == "slack"
        assert data[0]["auth_mode"] == "OAUTH2"

    @patch("app.routers.integrations._get_supabase_client")
    def test_list_providers_category_filter(self, mock_get_client, client):
        mock_client = MagicMock()
        mock_client.table.return_value = _mock_supabase_table(data=[])
        mock_get_client.return_value = mock_client

        resp = client.get("/api/v1/integrations/providers?category=crm")
        assert resp.status_code == 200
        # Verify eq was called with category filter
        mock_client.table.return_value.eq.assert_any_call("category", "crm")

    @patch("app.routers.integrations._get_supabase_client")
    def test_get_provider_found(self, mock_get_client, client):
        provider = {
            "provider_key": "github",
            "display_name": "GitHub",
            "description": "Code hosting",
            "logo_url": "",
            "category": "devtools",
            "auth_mode": "OAUTH2",
            "authorization_url": "https://github.com/login/oauth/authorize",
            "token_url": "https://github.com/login/oauth/access_token",
            "scope": "repo",
            "proxy_base_url": "https://api.github.com",
            "config": {},
            "is_enabled": True,
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
        }
        mock_client = MagicMock()
        mock_client.table.return_value = _mock_supabase_table(data=[provider])
        mock_get_client.return_value = mock_client

        resp = client.get("/api/v1/integrations/providers/github")
        assert resp.status_code == 200
        assert resp.json()["provider_key"] == "github"

    @patch("app.routers.integrations._get_supabase_client")
    def test_get_provider_not_found(self, mock_get_client, client):
        mock_client = MagicMock()
        mock_client.table.return_value = _mock_supabase_table(data=[])
        mock_get_client.return_value = mock_client

        resp = client.get("/api/v1/integrations/providers/nonexistent")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Connection Tests
# ---------------------------------------------------------------------------

class TestConnections:

    @patch("app.routers.integrations._get_supabase_client")
    def test_list_connections_empty(self, mock_get_client, client):
        mock_client = MagicMock()
        mock_client.table.return_value = _mock_supabase_table(data=[])
        mock_get_client.return_value = mock_client

        resp = client.get("/api/v1/integrations/connections?user_id=test-user")
        assert resp.status_code == 200
        assert resp.json() == []

    @patch("app.routers.integrations._get_supabase_client")
    def test_get_connection_not_found(self, mock_get_client, client):
        mock_client = MagicMock()
        mock_client.table.return_value = _mock_supabase_table(data=[])
        mock_get_client.return_value = mock_client

        resp = client.get("/api/v1/integrations/connections/conn_nonexistent")
        assert resp.status_code == 404

    @patch("app.routers.integrations._get_supabase_client")
    def test_delete_connection_not_found(self, mock_get_client, client):
        mock_client = MagicMock()
        mock_client.table.return_value = _mock_supabase_table(data=[])
        mock_get_client.return_value = mock_client

        resp = client.delete("/api/v1/integrations/connections/conn_nonexistent")
        assert resp.status_code == 404

    @patch("app.routers.integrations.is_encryption_available", return_value=True)
    @patch("app.routers.integrations.encrypt_api_key")
    @patch("app.routers.integrations._get_supabase_client")
    def test_create_api_key_connection(self, mock_get_client, mock_encrypt, mock_enc_avail, client):
        mock_encrypt.return_value = "encrypted_key_value"

        provider_row = {"provider_key": "openai", "auth_mode": "API_KEY"}
        connection_row = {
            "connection_id": "conn_test123",
            "user_id": "user-1",
            "provider_key": "openai",
            "display_name": "My OpenAI",
            "account_id": "",
            "account_email": "",
            "status": "active",
            "status_message": "",
            "scopes": "",
            "metadata": {},
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
        }

        mock_client = MagicMock()

        # First call: provider lookup (select provider)
        provider_chain = _mock_supabase_table(data=[provider_row])
        # Second call: connection insert
        conn_chain = _mock_supabase_table(data=[connection_row])
        # Third call: credential insert
        cred_chain = _mock_supabase_table(data=[{}])

        mock_client.table.side_effect = [
            provider_chain,   # providers table select
            conn_chain,       # connections table insert
            cred_chain,       # credentials table insert
        ]
        mock_get_client.return_value = mock_client

        resp = client.post("/api/v1/integrations/connections/api-key", json={
            "user_id": "user-1",
            "provider_key": "openai",
            "display_name": "My OpenAI",
            "api_key": "sk-test-key-12345",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["provider_key"] == "openai"
        assert data["status"] == "active"

    @patch("app.routers.integrations.is_encryption_available", return_value=False)
    def test_create_api_key_no_encryption(self, mock_enc, client):
        resp = client.post("/api/v1/integrations/connections/api-key", json={
            "user_id": "user-1",
            "provider_key": "openai",
            "api_key": "sk-test",
        })
        assert resp.status_code == 503

    def test_create_api_key_missing_key(self, client):
        resp = client.post("/api/v1/integrations/connections/api-key", json={
            "user_id": "user-1",
            "provider_key": "openai",
        })
        # Should fail with 400 (no api_key) or 503 (no encryption)
        assert resp.status_code in (400, 503)


# ---------------------------------------------------------------------------
# OAuth Flow Tests
# ---------------------------------------------------------------------------

class TestOAuth:

    @patch("app.routers.integrations._get_supabase_client")
    def test_authorize_provider_not_found(self, mock_get_client, client):
        mock_client = MagicMock()
        mock_client.table.return_value = _mock_supabase_table(data=[])
        mock_get_client.return_value = mock_client

        resp = client.get(
            "/api/v1/integrations/oauth/authorize/nonexistent"
            "?user_id=test&redirect_uri=http://localhost:3000/callback"
        )
        assert resp.status_code == 404

    @patch("app.routers.integrations._get_supabase_client")
    def test_authorize_non_oauth_provider(self, mock_get_client, client):
        provider = {
            "provider_key": "openai",
            "display_name": "OpenAI",
            "auth_mode": "API_KEY",
            "authorization_url": "",
            "token_url": "",
            "scope": "",
            "config": {},
            "is_enabled": True,
        }
        mock_client = MagicMock()
        mock_client.table.return_value = _mock_supabase_table(data=[provider])
        mock_get_client.return_value = mock_client

        resp = client.get(
            "/api/v1/integrations/oauth/authorize/openai"
            "?user_id=test&redirect_uri=http://localhost:3000/callback"
        )
        assert resp.status_code == 400

    def test_oauth_callback_invalid_state(self, client):
        resp = client.get("/api/v1/integrations/oauth/callback?code=test&state=invalid_state")
        # Should fail — either 400 (invalid state) or 503 (no encryption)
        assert resp.status_code in (400, 503)


# ---------------------------------------------------------------------------
# Credential Tests
# ---------------------------------------------------------------------------

class TestCredentials:

    @patch("app.routers.integrations.is_encryption_available", return_value=True)
    @patch("app.routers.integrations._get_supabase_client")
    def test_get_credentials_not_found(self, mock_get_client, mock_enc, client):
        mock_client = MagicMock()
        mock_client.table.return_value = _mock_supabase_table(data=[])
        mock_get_client.return_value = mock_client

        resp = client.get("/api/v1/integrations/connections/conn_test/credentials")
        assert resp.status_code == 404

    @patch("app.routers.integrations.is_encryption_available", return_value=False)
    def test_get_credentials_no_encryption(self, mock_enc, client):
        resp = client.get("/api/v1/integrations/connections/conn_test/credentials")
        assert resp.status_code == 503


# ---------------------------------------------------------------------------
# Model Tests
# ---------------------------------------------------------------------------

class TestModels:

    def test_auth_mode_enum(self):
        from app.models import AuthMode
        assert AuthMode.OAUTH2 == "OAUTH2"
        assert AuthMode.API_KEY == "API_KEY"

    def test_connection_status_enum(self):
        from app.models import ConnectionStatus
        assert ConnectionStatus.ACTIVE == "active"
        assert ConnectionStatus.EXPIRED == "expired"

    def test_integration_provider_model(self):
        from app.models import IntegrationProvider
        p = IntegrationProvider(
            provider_key="test",
            display_name="Test Provider",
            category="testing",
            auth_mode="OAUTH2",
        )
        assert p.provider_key == "test"
        assert p.is_enabled is True

    def test_integration_connection_model(self):
        from app.models import IntegrationConnection
        c = IntegrationConnection(
            connection_id="conn_test",
            user_id="user-1",
            provider_key="test",
        )
        assert c.status == "active"


# ---------------------------------------------------------------------------
# Seed Data Tests
# ---------------------------------------------------------------------------

class TestSeedData:

    def test_seed_has_100_providers(self):
        from app.integration_providers_seed import INTEGRATION_PROVIDERS
        assert len(INTEGRATION_PROVIDERS) == 100

    def test_seed_provider_keys_unique(self):
        from app.integration_providers_seed import INTEGRATION_PROVIDERS
        keys = [p["provider_key"] for p in INTEGRATION_PROVIDERS]
        assert len(keys) == len(set(keys)), f"Duplicate keys: {[k for k in keys if keys.count(k) > 1]}"

    def test_seed_all_have_required_fields(self):
        from app.integration_providers_seed import INTEGRATION_PROVIDERS
        for p in INTEGRATION_PROVIDERS:
            assert "provider_key" in p, f"Missing provider_key in {p.get('display_name')}"
            assert "display_name" in p, f"Missing display_name in {p.get('provider_key')}"
            assert "category" in p, f"Missing category in {p.get('provider_key')}"
            assert "auth_mode" in p, f"Missing auth_mode in {p.get('provider_key')}"
            assert p["auth_mode"] in ("OAUTH2", "API_KEY", "BASIC", "NONE"), \
                f"Invalid auth_mode '{p['auth_mode']}' for {p['provider_key']}"

    def test_seed_oauth_providers_have_urls(self):
        from app.integration_providers_seed import INTEGRATION_PROVIDERS
        for p in INTEGRATION_PROVIDERS:
            if p["auth_mode"] == "OAUTH2":
                assert p.get("authorization_url"), \
                    f"OAuth provider {p['provider_key']} missing authorization_url"
                assert p.get("token_url"), \
                    f"OAuth provider {p['provider_key']} missing token_url"

    def test_seed_categories_present(self):
        from app.integration_providers_seed import INTEGRATION_PROVIDERS
        categories = set(p["category"] for p in INTEGRATION_PROVIDERS)
        expected = {"google", "microsoft", "video", "communication", "crm",
                    "project-management", "devtools", "social", "payments",
                    "analytics", "ai", "database"}
        assert expected.issubset(categories), f"Missing categories: {expected - categories}"
