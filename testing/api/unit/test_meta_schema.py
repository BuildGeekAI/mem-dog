"""Unit tests for meta_schema: normalize_meta_data, accessor helpers, build_meta_data."""

import sys
import types
from unittest.mock import MagicMock

# Stub out heavy deps (same as test_agent_routing.py)
if "requests" not in sys.modules:
    stub = types.ModuleType("requests")
    stub.get = MagicMock()
    stub.post = MagicMock()
    stub.delete = MagicMock()

    class _RE(Exception):
        pass

    stub.RequestException = _RE
    adapters = types.ModuleType("requests.adapters")
    adapters.HTTPAdapter = MagicMock()
    stub.adapters = adapters
    stub.Session = MagicMock()
    sys.modules["requests"] = stub
    sys.modules["requests.adapters"] = adapters

import pytest

from webhook.processor.webhook_agent.meta_schema import (
    normalize_meta_data,
    build_meta_data,
    set_field,
    get_user_id,
    get_owner,
    get_mime_type,
    get_source_type,
    get_channel_message,
    get_data_id,
    get_url,
    get_download_url,
    get_gcs_uri,
    get_is_downloaded,
    get_trace_memory_id,
    get_memory,
    get_session_id,
    get_version,
    get_version_label,
    get_prompt,
    get_crawl,
    _KNOWN_FLAT_KEYS,
)


class TestNormalizeMetaData:
    def test_flat_to_nested(self):
        flat = {
            "user_id": "alice",
            "mime_type": "application/pdf",
            "data_id": "d1",
            "url": "https://example.com/f.pdf",
            "is_downloaded": True,
            "trace_memory_id": "tm1",
            "memory": {"timeline": ["tl-1"]},
        }
        nested = normalize_meta_data(flat)
        assert nested["identity"]["user_id"] == "alice"
        assert nested["content"]["mime_type"] == "application/pdf"
        assert nested["access"]["data_id"] == "d1"
        assert nested["access"]["url"] == "https://example.com/f.pdf"
        assert nested["access"]["is_downloaded"] is True
        assert nested["tracing"]["trace_memory_id"] == "tm1"
        assert nested["tracing"]["memory"] == {"timeline": ["tl-1"]}

    def test_mimetype_merged_to_mime_type(self):
        flat = {"mimetype": "image/png"}
        nested = normalize_meta_data(flat)
        assert nested["content"]["mime_type"] == "image/png"
        assert "mimetype" not in nested

    def test_mime_type_not_overwritten_by_mimetype(self):
        flat = {"mime_type": "application/pdf", "mimetype": "image/png"}
        nested = normalize_meta_data(flat)
        assert nested["content"]["mime_type"] == "application/pdf"

    def test_memory_list_migrated(self):
        flat = {"memory_list": ["tl-1", "sess-1"]}
        nested = normalize_meta_data(flat)
        assert nested["tracing"]["memory"] == {"other": ["tl-1", "sess-1"]}

    def test_removed_fields_dropped(self):
        flat = {
            "user_id": "alice",
            "user_name": "Alice",
            "name": "test",
            "description": "desc",
            "tags": ["a"],
            "subject": "subj",
            "llm_classification": {"x": 1},
            "participants": ["bob"],
            "envelope_id": "e1",
            "timestamp": "2024-01-01",
            "services": {},
            "device": "phone",
        }
        nested = normalize_meta_data(flat)
        for removed in ("user_name", "name", "description", "tags", "subject",
                        "llm_classification", "participants", "envelope_id",
                        "timestamp", "services", "device"):
            assert removed not in nested
            for grp in ("identity", "content", "access", "tracing", "routing"):
                assert removed not in nested.get(grp, {})

    def test_preserves_existing_nested(self):
        meta = {
            "identity": {"user_id": "bob"},
            "content": {"mime_type": "text/plain"},
            "access": {"data_id": "d2"},
        }
        nested = normalize_meta_data(meta)
        assert nested["identity"]["user_id"] == "bob"
        assert nested["content"]["mime_type"] == "text/plain"
        assert nested["access"]["data_id"] == "d2"

    def test_trace_context_preserved(self):
        flat = {"__trace_context__": {"trace_id": "t1", "span_id": "s1"}}
        nested = normalize_meta_data(flat)
        assert nested["__trace_context__"]["trace_id"] == "t1"

    def test_unknown_keys_preserved(self):
        flat = {"custom_field": "value"}
        nested = normalize_meta_data(flat)
        assert nested["custom_field"] == "value"

    def test_already_nested_is_idempotent(self):
        meta = {
            "identity": {"user_id": "alice"},
            "content": {"mime_type": "application/pdf"},
            "access": {"data_id": "d1", "is_downloaded": True},
            "tracing": {"trace_memory_id": "tm1"},
            "__trace_context__": {"trace_id": "t1"},
        }
        result = normalize_meta_data(meta)
        assert result == meta


class TestAccessorHelpers:
    def test_nested_access(self):
        meta = {
            "identity": {"user_id": "alice", "owner": {"user": {"user_id": "alice"}}},
            "content": {"mime_type": "application/pdf", "source_type": "document",
                        "channel_message": {"text": "hi"}},
            "access": {"data_id": "d1", "url": "https://x.com", "download_url": "https://dl.com",
                       "gcs_uri": "gs://b/o", "is_downloaded": True},
            "tracing": {"trace_memory_id": "tm1", "memory": {"tl": ["a"]},
                        "session_id": "s1", "version": 2, "version_label": "v2"},
            "routing": {"prompt": "test", "crawl": {"max_depth": 1}},
        }
        assert get_user_id(meta) == "alice"
        assert get_owner(meta)["user"]["user_id"] == "alice"
        assert get_mime_type(meta) == "application/pdf"
        assert get_source_type(meta) == "document"
        assert get_channel_message(meta)["text"] == "hi"
        assert get_data_id(meta) == "d1"
        assert get_url(meta) == "https://x.com"
        assert get_download_url(meta) == "https://dl.com"
        assert get_gcs_uri(meta) == "gs://b/o"
        assert get_is_downloaded(meta) is True
        assert get_trace_memory_id(meta) == "tm1"
        assert get_memory(meta) == {"tl": ["a"]}
        assert get_session_id(meta) == "s1"
        assert get_version(meta) == 2
        assert get_version_label(meta) == "v2"
        assert get_prompt(meta) == "test"
        assert get_crawl(meta) == {"max_depth": 1}

    def test_flat_fallback(self):
        meta = {
            "user_id": "bob",
            "mime_type": "text/plain",
            "data_id": "d2",
            "url": "https://y.com",
            "is_downloaded": False,
            "trace_memory_id": "tm2",
        }
        assert get_user_id(meta) == "bob"
        assert get_mime_type(meta) == "text/plain"
        assert get_data_id(meta) == "d2"
        assert get_url(meta) == "https://y.com"
        assert get_is_downloaded(meta) is False
        assert get_trace_memory_id(meta) == "tm2"

    def test_mimetype_fallback(self):
        meta = {"mimetype": "image/png"}
        assert get_mime_type(meta) == "image/png"

    def test_defaults(self):
        meta = {}
        assert get_user_id(meta) is None
        assert get_owner(meta) is None
        assert get_mime_type(meta) is None
        assert get_data_id(meta) is None
        assert get_is_downloaded(meta) is False
        assert get_version(meta) is None
        assert get_memory(meta) is None


class TestSetField:
    def test_sets_nested_field(self):
        meta = {}
        set_field(meta, "access", "data_id", "d1")
        assert meta["access"]["data_id"] == "d1"

    def test_adds_to_existing_group(self):
        meta = {"access": {"url": "https://x.com"}}
        set_field(meta, "access", "data_id", "d1")
        assert meta["access"]["url"] == "https://x.com"
        assert meta["access"]["data_id"] == "d1"


class TestBuildMetaData:
    def test_basic_build(self):
        result = build_meta_data(
            user_id="alice",
            mime_type="application/pdf",
            data_id="d1",
            is_downloaded=True,
            trace_memory_id="tm1",
        )
        assert result["identity"]["user_id"] == "alice"
        assert result["content"]["mime_type"] == "application/pdf"
        assert result["access"]["data_id"] == "d1"
        assert result["access"]["is_downloaded"] is True
        assert result["tracing"]["trace_memory_id"] == "tm1"

    def test_minimal_build(self):
        result = build_meta_data()
        assert result["access"]["is_downloaded"] is False
        assert "identity" not in result
        assert "content" not in result

    def test_with_trace_context(self):
        result = build_meta_data(
            user_id="bob",
            trace_context={"trace_id": "t1", "span_id": "s1"},
        )
        assert result["__trace_context__"]["trace_id"] == "t1"

    def test_all_fields(self):
        result = build_meta_data(
            user_id="alice",
            owner={"user": {"user_id": "alice"}},
            mime_type="application/pdf",
            source_type="document",
            channel_message={"text": "hi"},
            data_id="d1",
            url="https://x.com",
            download_url="https://dl.com",
            gcs_uri="gs://b/o",
            is_downloaded=True,
            trace_memory_id="tm1",
            memory={"timeline": ["tl-1"]},
            session_id="s1",
            version=2,
            version_label="v2",
            prompt="test",
            crawl={"max_depth": 1},
        )
        assert get_user_id(result) == "alice"
        assert get_owner(result)["user"]["user_id"] == "alice"
        assert get_prompt(result) == "test"
        assert get_crawl(result) == {"max_depth": 1}


class TestKnownFlatKeys:
    def test_includes_all_flat_keys(self):
        expected = {
            "user_id", "owner", "mime_type", "mimetype", "source_type",
            "channel_message", "data_id", "url", "download_url", "gcs_uri",
            "is_downloaded", "trace_memory_id", "memory", "memory_list",
            "session_id", "version", "version_label", "prompt", "crawl",
            "__trace_context__",
        }
        assert expected.issubset(_KNOWN_FLAT_KEYS)

    def test_includes_removed_fields(self):
        removed = {
            "user_name", "name", "description", "tags", "subject",
            "llm_classification", "participants", "envelope_id",
            "timestamp", "services", "device",
        }
        assert removed.issubset(_KNOWN_FLAT_KEYS)
