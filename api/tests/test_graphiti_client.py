"""Tests for the Graphiti client module."""

import os
import pytest
from app.graphiti_client import is_graphiti_enabled


class TestGraphitiEnabled:
    def test_disabled_by_default(self, monkeypatch):
        monkeypatch.delenv("NEO4J_URI", raising=False)
        assert is_graphiti_enabled() is False

    def test_enabled_when_uri_set(self, monkeypatch):
        monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
        assert is_graphiti_enabled() is True

    def test_empty_uri_is_disabled(self, monkeypatch):
        monkeypatch.setenv("NEO4J_URI", "")
        assert is_graphiti_enabled() is False
