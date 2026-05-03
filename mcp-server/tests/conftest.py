"""Test fixtures for MCP server tests."""

import pytest

from mem_dog_client.simple import MemDog


@pytest.fixture
def api_key():
    return "md_test_key_123"


@pytest.fixture
def client(api_key):
    return MemDog(base_url="http://testserver:8080", api_key=api_key, timeout=5.0)
