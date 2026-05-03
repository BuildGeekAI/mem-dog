"""Unit tests for the identity resolver."""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest
import respx

from app.identity import clear_cache, resolve_user_id


@pytest.fixture(autouse=True)
def _clean_cache():
    clear_cache()
    yield
    clear_cache()


@pytest.fixture(autouse=True)
def _set_config():
    with patch("app.identity.config") as cfg:
        cfg.MEM_DOG_API_URL = "http://test-api:8080"
        cfg.DEFAULT_USER_ID = "default-uid"
        yield cfg


class TestResolveUserId:
    @respx.mock
    @pytest.mark.asyncio
    async def test_found(self):
        respx.get(
            "http://test-api:8080/api/v1/channel-identities/by-channel/email/alice@test.com"
        ).mock(return_value=httpx.Response(200, json={"user_id": "user-alice"}))

        uid = await resolve_user_id("email", "alice@test.com")
        assert uid == "user-alice"

    @respx.mock
    @pytest.mark.asyncio
    async def test_not_found_returns_default(self):
        respx.get(
            "http://test-api:8080/api/v1/channel-identities/by-channel/email/unknown@test.com"
        ).mock(return_value=httpx.Response(404))

        uid = await resolve_user_id("email", "unknown@test.com")
        assert uid == "default-uid"

    @pytest.mark.asyncio
    async def test_empty_unique_id_returns_default(self):
        uid = await resolve_user_id("email", "")
        assert uid == "default-uid"

    @respx.mock
    @pytest.mark.asyncio
    async def test_caches_result(self):
        route = respx.get(
            "http://test-api:8080/api/v1/channel-identities/by-channel/email/cached@test.com"
        ).mock(return_value=httpx.Response(200, json={"user_id": "user-cached"}))

        uid1 = await resolve_user_id("email", "cached@test.com")
        uid2 = await resolve_user_id("email", "cached@test.com")
        assert uid1 == uid2 == "user-cached"
        assert route.call_count == 1

    @respx.mock
    @pytest.mark.asyncio
    async def test_api_error_returns_default(self):
        respx.get(
            "http://test-api:8080/api/v1/channel-identities/by-channel/email/err@test.com"
        ).mock(side_effect=httpx.ConnectError("conn refused"))

        uid = await resolve_user_id("email", "err@test.com")
        assert uid == "default-uid"
