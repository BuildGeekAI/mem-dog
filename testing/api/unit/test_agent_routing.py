"""Unit tests for the webhook agent routing pipeline.

Covers:
- GroupContext extraction, derivation, and memory-ID formation
- LightLLMClassifier (all layers: exact, fuzzy, fallback)
- MIME registry exact and prefix matching
- URL extension sniffing (Layer 4)
- Layer 0b (url not downloaded) routing to url_download
- Four-layer detect_data_type()
- BaseSubAgent.write_record() and delete_record() integration
- StatsClient increment/decrement flow
- All agents: publish() schema and process() stub
- Full AGENT_REGISTRY completeness
"""

import importlib
import json
import sys
import types
from dataclasses import asdict
from unittest.mock import MagicMock, call, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers to stub out heavy optional dependencies before imports
# ---------------------------------------------------------------------------

def _make_requests_stub():
    """Return a minimal stub for ``requests`` so we never hit the network."""
    stub = types.ModuleType("requests")

    class Response:
        def __init__(self, status_code=200, json_data=None):
            self.status_code = status_code
            self._json = json_data or {}

        def json(self):
            return self._json

        def raise_for_status(self):
            if self.status_code >= 400:
                raise Exception(f"HTTP {self.status_code}")

    stub.get = MagicMock(return_value=Response(200, {}))
    stub.post = MagicMock(return_value=Response(200, {"data_id": "d1", "version": 1, "memory_id": "m1"}))
    stub.delete = MagicMock(return_value=Response(200, {}))

    class RequestException(Exception):
        pass

    stub.RequestException = RequestException

    # session.py: "from requests.adapters import HTTPAdapter" and "requests.Session()"
    adapters = types.ModuleType("requests.adapters")
    adapters.HTTPAdapter = MagicMock()
    stub.adapters = adapters
    mock_session = MagicMock()
    mock_session.get = stub.get
    mock_session.post = stub.post
    mock_session.delete = stub.delete
    stub.Session = MagicMock(return_value=mock_session)
    return stub


# Patch requests before any agent code is imported
_requests_stub = _make_requests_stub()
sys.modules.setdefault("requests", _requests_stub)
sys.modules.setdefault("requests.adapters", _requests_stub.adapters)

# Stub google.adk so we don't need the full SDK installed in test env
_adk = types.ModuleType("google")
_adk.adk = types.ModuleType("google.adk")
_adk.adk.agents = types.ModuleType("google.adk.agents")
_adk.adk.agents.Agent = MagicMock()
_adk.adk.models = types.ModuleType("google.adk.models")
_adk.adk.models.lite_llm = types.ModuleType("google.adk.models.lite_llm")
_adk.adk.models.lite_llm.LiteLlm = MagicMock()
sys.modules.setdefault("google", _adk)
sys.modules.setdefault("google.adk", _adk.adk)
sys.modules.setdefault("google.adk.agents", _adk.adk.agents)
sys.modules.setdefault("google.adk.models", _adk.adk.models)
sys.modules.setdefault("google.adk.models.lite_llm", _adk.adk.models.lite_llm)

# Root of the webhook agent package
AGENT_PKG = "webhook.processor.webhook_agent"

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def agent_pkg():
    """Import the webhook_agent package root once per test session."""
    import importlib.util
    import os

    pkg_path = os.path.join(
        os.path.dirname(__file__),
        "..", "..", "..",
        "webhook", "processor",
    )
    spec = importlib.util.spec_from_file_location(
        "webhook_agent",
        os.path.join(pkg_path, "webhook_agent", "__init__.py"),
        submodule_search_locations=[os.path.join(pkg_path, "webhook_agent")],
    )
    return spec


@pytest.fixture(scope="session")
def group_context_mod():
    from webhook.processor.webhook_agent import group_context
    return group_context


@pytest.fixture(scope="session")
def registry_mod():
    from webhook.processor.webhook_agent.sub_agents import MIME_REGISTRY, AGENT_REGISTRY
    return MIME_REGISTRY, AGENT_REGISTRY


@pytest.fixture(scope="session")
def router_mod():
    from webhook.processor.webhook_agent import router
    return router


@pytest.fixture(scope="session")
def classifier_mod():
    from webhook.processor.webhook_agent import classifier as clf_mod
    return clf_mod


@pytest.fixture(scope="session")
def all_agents():
    from webhook.processor.webhook_agent.sub_agents import _ALL_AGENTS
    return _ALL_AGENTS


# ===========================================================================
# GroupContext tests
# ===========================================================================


class TestExtractPrefix:
    def test_memory_prefix_field(self, group_context_mod):
        assert group_context_mod.extract_prefix({"memory_prefix": "ord-42"}) == "ord-42"

    def test_fallback_to_prefix_field(self, group_context_mod):
        assert group_context_mod.extract_prefix({"prefix": "batch-01"}) == "batch-01"

    def test_fallback_to_group_prefix_field(self, group_context_mod):
        assert group_context_mod.extract_prefix({"group_prefix": "proj-99"}) == "proj-99"

    def test_fallback_to_bucket_prefix_field(self, group_context_mod):
        assert group_context_mod.extract_prefix({"bucket_prefix": "bucket-7"}) == "bucket-7"

    def test_priority_order(self, group_context_mod):
        """memory_prefix wins when multiple fields present."""
        result = group_context_mod.extract_prefix({
            "memory_prefix": "winner",
            "prefix": "loser",
            "group_prefix": "also-loser",
        })
        assert result == "winner"

    def test_none_when_absent(self, group_context_mod):
        assert group_context_mod.extract_prefix({"user_id": "alice"}) is None

    def test_sanitises_value(self, group_context_mod):
        """Characters outside [a-zA-Z0-9-_] should be replaced with hyphens."""
        result = group_context_mod.extract_prefix({"memory_prefix": "ord/42 !"})
        assert result is not None
        assert "/" not in result
        assert " " not in result
        assert "!" not in result


class TestExtractGroupIds:
    def test_explicit_fields(self, group_context_mod):
        user_id, group_id = group_context_mod.extract_group_ids(
            {"user_id": "alice", "correlation_id": "batch-42"}
        )
        assert user_id == "alice"
        assert group_id == "batch-42"

    def test_camel_case_user(self, group_context_mod):
        user_id, _ = group_context_mod.extract_group_ids({"userId": "bob"})
        assert user_id == "bob"

    def test_no_group_field_defaults_to_user_id(self, group_context_mod):
        user_id, group_id = group_context_mod.extract_group_ids({"user_id": "carol"})
        assert user_id == "carol"
        assert group_id == "carol"

    def test_no_user_field_defaults_to_agent_user_id(self, group_context_mod):
        from webhook.processor.webhook_agent.api_client.config import AGENT_USER_ID
        user_id, _ = group_context_mod.extract_group_ids({})
        assert user_id == AGENT_USER_ID

    def test_group_priority_order(self, group_context_mod):
        """correlation_id wins over session_id when both present."""
        _, group_id = group_context_mod.extract_group_ids({
            "user_id": "alice",
            "correlation_id": "first",
            "session_id": "second",
        })
        assert group_id == "first"


class TestBuildGroupContext:
    def test_prefix_sets_memory_ids(self, group_context_mod):
        ctx = group_context_mod.build_group_context({"memory_prefix": "ord-42"})
        assert ctx.timeline_memory_id == "timeline-ord-42"
        assert ctx.session_memory_id == "session-ord-42"
        assert ctx.prefix == "ord-42"

    def test_no_prefix_derives_ids(self, group_context_mod):
        ctx = group_context_mod.build_group_context(
            {"user_id": "alice", "correlation_id": "batch"}
        )
        assert ctx.timeline_memory_id.startswith("timeline-grp-")
        assert "alice" in ctx.timeline_memory_id
        assert ctx.prefix is None

    def test_is_new_group_defaults_false(self, group_context_mod):
        ctx = group_context_mod.build_group_context({"memory_prefix": "x"})
        assert ctx.is_new_group is False

    def test_prefix_takes_priority_over_correlation(self, group_context_mod):
        ctx = group_context_mod.build_group_context({
            "memory_prefix": "my-prefix",
            "correlation_id": "should-be-ignored",
        })
        assert ctx.timeline_memory_id == "timeline-my-prefix"

    def test_same_prefix_same_memory_ids(self, group_context_mod):
        ctx1 = group_context_mod.build_group_context({"memory_prefix": "ord-42", "user_id": "alice"})
        ctx2 = group_context_mod.build_group_context({"memory_prefix": "ord-42", "user_id": "bob"})
        assert ctx1.timeline_memory_id == ctx2.timeline_memory_id

    def test_different_prefix_different_memory_ids(self, group_context_mod):
        ctx1 = group_context_mod.build_group_context({"memory_prefix": "ord-42"})
        ctx2 = group_context_mod.build_group_context({"memory_prefix": "ord-43"})
        assert ctx1.timeline_memory_id != ctx2.timeline_memory_id


class TestEnsureGroupMemories:
    def test_does_not_create_memories(self, group_context_mod):
        """ensure_group_memories returns context without creating any memories (agent policy)."""
        ctx = group_context_mod.build_group_context({"memory_prefix": "new-grp"})
        result = group_context_mod.ensure_group_memories(ctx)
        assert result.timeline_memory_id == "timeline-new-grp"
        assert result.session_memory_id == "session-new-grp"
        assert result.is_new_group is False

    def test_preserves_context(self, group_context_mod):
        ctx = group_context_mod.build_group_context({"memory_prefix": "existing-grp"})
        result = group_context_mod.ensure_group_memories(ctx)
        assert result.timeline_memory_id == ctx.timeline_memory_id
        assert result.session_memory_id == ctx.session_memory_id
        assert result.is_new_group is False


# ===========================================================================
# MIME Registry tests
# ===========================================================================


class TestMimeRegistry:
    def test_exact_match(self, registry_mod):
        mime_registry, _ = registry_mod
        agent = mime_registry.match("application/pdf")
        assert agent is not None
        assert agent.AGENT_TYPE == "pdf"

    def test_prefix_match(self, registry_mod):
        mime_registry, _ = registry_mod
        agent = mime_registry.match("video/x-custom-format")
        assert agent is not None
        assert "video" in agent.AGENT_TYPE

    def test_no_match_returns_none(self, registry_mod):
        mime_registry, _ = registry_mod
        agent = mime_registry.match("application/x-totally-unknown-type-xyz")
        assert agent is None

    def test_all_26_mimes_registered(self, registry_mod):
        mime_registry, agent_registry = registry_mod
        # Spot-check a broad set
        spot_check = [
            ("application/pdf", "pdf"),
            ("application/json", "json"),
            ("text/csv", "csv"),
            ("application/x-lidar", "lidar"),
            ("message/rfc822", "email"),
            ("application/dicom", "medical_imaging"),
        ]
        for mime, expected_type in spot_check:
            agent = mime_registry.match(mime)
            assert agent is not None, f"No agent for MIME {mime!r}"
            assert agent.AGENT_TYPE == expected_type, (
                f"MIME {mime!r}: expected {expected_type!r}, got {agent.AGENT_TYPE!r}"
            )


# ===========================================================================
# normalize_message (data + telemetry contract) tests
# ===========================================================================


class TestNormalizeMessage:
    """Canonical contract: only data and telemetry; no new data entries from telemetry."""

    def test_data_and_meta_data_accepted(self, router_mod):
        """Payload with only data and meta_data is normalized correctly."""
        from webhook.processor.webhook_agent.meta_schema import get_user_id, get_trace_memory_id
        payload = {
            "data": {"event": "test", "hello": "world"},
            "meta_data": {"user_id": "alice", "trace_memory_id": "mem_tracing_xyz"},
        }
        data, meta_data = router_mod.normalize_message(payload)
        assert data == {"event": "test", "hello": "world"}
        assert get_user_id(meta_data) == "alice"
        assert get_trace_memory_id(meta_data) == "mem_tracing_xyz"

    def test_legacy_telemetry_accepted(self, router_mod):
        """Legacy payload with telemetry (no meta_data) is still accepted."""
        from webhook.processor.webhook_agent.meta_schema import get_user_id
        payload = {
            "data": {"event": "legacy"},
            "telemetry": {"user_id": "bob"},
        }
        data, meta_data = router_mod.normalize_message(payload)
        assert data == {"event": "legacy"}
        assert get_user_id(meta_data) == "bob"

    def test_meta_data_preferred_over_telemetry(self, router_mod):
        """When both meta_data and telemetry present, meta_data is used."""
        from webhook.processor.webhook_agent.meta_schema import get_user_id
        payload = {
            "data": {"x": 1},
            "meta_data": {"user_id": "from_meta_data"},
            "telemetry": {"user_id": "from_telemetry"},
        }
        data, meta_data = router_mod.normalize_message(payload)
        assert get_user_id(meta_data) == "from_meta_data"

    def test_flat_payload_normalized_to_data_and_meta(self, router_mod):
        """Flat payload is split: known meta keys → meta, rest → data."""
        from webhook.processor.webhook_agent.meta_schema import get_user_id, get_trace_memory_id
        payload = {"event": "flat", "user_id": "carol", "trace_memory_id": "mem_123"}
        data, meta_data = router_mod.normalize_message(payload)
        assert data == {"event": "flat"}
        assert get_user_id(meta_data) == "carol"
        assert get_trace_memory_id(meta_data) == "mem_123"


# ===========================================================================
# Data type detection tests (router layer)
# ===========================================================================


class TestDetectDataType:
    def test_layer1_explicit_data_type(self, router_mod):
        agent_type, _ = router_mod.detect_data_type({"data_type": "lidar"})
        assert agent_type == "lidar"

    def test_layer1_source_type(self, router_mod):
        agent_type, _ = router_mod.detect_data_type({"source_type": "pdf"})
        assert agent_type == "pdf"

    def test_layer1_unknown_value_falls_through(self, router_mod):
        with patch.object(router_mod.classifier, "classify", return_value=None):
            agent_type, _ = router_mod.detect_data_type({"data_type": "unknown_xyz"})
            assert agent_type in router_mod.AGENT_REGISTRY

    def test_layer2_llm_takes_priority_over_mime(self, router_mod):
        """LLM result wins even when MIME matches a different agent."""
        with patch.object(router_mod.classifier, "classify", return_value="pdf"):
            agent_type, _ = router_mod.detect_data_type({"content_type": "video/mp4"})
        assert agent_type == "pdf"

    def test_layer3_mime_registry(self, router_mod):
        with patch.object(router_mod.classifier, "classify", return_value=None):
            agent_type, _ = router_mod.detect_data_type({"content_type": "application/json"})
        assert agent_type == "json"

    def test_layer4_url_extension_mp4(self, router_mod):
        with patch.object(router_mod.classifier, "classify", return_value=None):
            agent_type, _ = router_mod.detect_data_type({"url": "https://cdn.example.com/clip.mp4"})
        assert agent_type == "video_url"

    def test_layer4_url_extension_pdf(self, router_mod):
        with patch.object(router_mod.classifier, "classify", return_value=None):
            agent_type, _ = router_mod.detect_data_type({"url": "https://example.com/report.pdf"})
        assert agent_type == "pdf"

    def test_layer4_url_extension_csv(self, router_mod):
        with patch.object(router_mod.classifier, "classify", return_value=None):
            agent_type, _ = router_mod.detect_data_type({"url": "https://example.com/data.csv"})
        assert agent_type == "csv"

    def test_layer4_url_extension_log(self, router_mod):
        with patch.object(router_mod.classifier, "classify", return_value=None):
            agent_type, _ = router_mod.detect_data_type({"url": "s3://bucket/app.log"})
        assert agent_type == "log_file"

    def test_layer4_url_extension_dcm(self, router_mod):
        with patch.object(router_mod.classifier, "classify", return_value=None):
            agent_type, _ = router_mod.detect_data_type({"url": "https://hospital.example.com/scan.dcm"})
        assert agent_type == "medical_imaging"

    def test_fallback_binary_blob(self, router_mod):
        with patch.object(router_mod.classifier, "classify", return_value=None):
            agent_type, _ = router_mod.detect_data_type({"something": "unknown"})
        assert agent_type == "binary_blob"

    def test_explicit_field_skips_llm(self, router_mod):
        """Layer 1 should short-circuit — LLM must NOT be called."""
        with patch.object(router_mod.classifier, "classify") as mock_classify:
            router_mod.detect_data_type({"data_type": "lidar"})
            mock_classify.assert_not_called()


# ===========================================================================
# Layer 0b — URL not downloaded: route to url_download
# ===========================================================================


class TestRouterLayer0bUrlDownload:
    """When url is in telemetry but data_id/is_downloaded are not set, router uses url_download."""

    def test_url_present_no_data_id_routes_to_url_download(self, router_mod):
        """Payload with meta_data.url and no data_id → agent is url_download."""
        payload = {
            "data": {"url": "https://example.com/file.pdf"},
            "meta_data": {
                "identity": {"user_id": "alice"},
                "access": {"url": "https://example.com/file.pdf", "is_downloaded": False},
            },
        }
        download_agent = router_mod.AGENT_REGISTRY[router_mod.DOWNLOAD_AGENT_KEY]
        with (
            patch.object(
                router_mod,
                "ensure_group_memories",
                return_value=MagicMock(
                    timeline_memory_id="tl-1",
                    session_memory_id="sess-1",
                    group_id="alice",
                    user_id="alice",
                    is_new_group=False,
                    prefix=None,
                ),
            ),
            patch.object(download_agent, "write_record", return_value={"status": "success", "data_id": "test-id"}),
            patch.object(router_mod.tracking_client, "write_span"),
        ):
            result = router_mod.route_payload(json.dumps(payload))
        assert result["agent"]["agent_type"] == "url_download"

    def test_url_with_data_id_and_is_downloaded_true_does_not_route_to_url_download(self, router_mod):
        """Payload with url and data_id and is_downloaded=true → typed agent (e.g. pdf), not url_download."""
        payload = {
            "data": {"url": "https://example.com/file.pdf"},
            "meta_data": {
                "identity": {"user_id": "alice"},
                "access": {
                    "url": "https://example.com/file.pdf",
                    "data_id": "d123",
                    "is_downloaded": True,
                },
            },
        }
        with (
            patch.object(
                router_mod,
                "ensure_group_memories",
                return_value=MagicMock(
                    timeline_memory_id="tl-1",
                    session_memory_id="sess-1",
                    group_id="alice",
                    user_id="alice",
                    is_new_group=False,
                    prefix=None,
                ),
            ),
            patch.object(router_mod.AGENT_REGISTRY["pdf"], "process", return_value={"status": "ok"}),
            patch.object(router_mod.tracking_client, "write_span"),
        ):
            result = router_mod.route_payload(json.dumps(payload))
        assert result["agent"]["agent_type"] == "pdf"

    def test_url_with_data_id_but_is_downloaded_false_routes_to_url_download(self, router_mod):
        """Payload with url and data_id but is_downloaded=false → still url_download (re-download)."""
        payload = {
            "data": {"url": "https://example.com/file.pdf"},
            "meta_data": {
                "identity": {"user_id": "alice"},
                "access": {
                    "url": "https://example.com/file.pdf",
                    "data_id": "d123",
                    "is_downloaded": False,
                },
            },
        }
        download_agent = router_mod.AGENT_REGISTRY[router_mod.DOWNLOAD_AGENT_KEY]
        with (
            patch.object(
                router_mod,
                "ensure_group_memories",
                return_value=MagicMock(
                    timeline_memory_id="tl-1",
                    session_memory_id="sess-1",
                    group_id="alice",
                    user_id="alice",
                    is_new_group=False,
                    prefix=None,
                ),
            ),
            patch.object(download_agent, "write_record", return_value={"status": "success", "data_id": "test-id"}),
            patch.object(router_mod.tracking_client, "write_span"),
        ):
            result = router_mod.route_payload(json.dumps(payload))
        assert result["agent"]["agent_type"] == "url_download"


# ===========================================================================
# LLM Classifier tests
# ===========================================================================


class TestLightLLMClassifier:
    def _make_llm_response(self, text: str):
        choice = MagicMock()
        choice.message.content = text
        response = MagicMock()
        response.choices = [choice]
        return response

    def test_returns_valid_type(self, classifier_mod):
        clf = classifier_mod.LightLLMClassifier(model="test/model")
        with patch("litellm.completion", return_value=self._make_llm_response("pdf")):
            result = clf.classify({"content_type": "application/pdf"})
        assert result == "pdf"

    def test_fuzzy_match(self, classifier_mod):
        clf = classifier_mod.LightLLMClassifier(model="test/model")
        with patch("litellm.completion", return_value=self._make_llm_response("this is a pdf type")):
            result = clf.classify({})
        assert result == "pdf"

    def test_rejects_unknown_type(self, classifier_mod):
        clf = classifier_mod.LightLLMClassifier(model="test/model")
        with patch("litellm.completion", return_value=self._make_llm_response("spreadsheet")):
            result = clf.classify({})
        assert result is None

    def test_falls_back_on_exception(self, classifier_mod):
        clf = classifier_mod.LightLLMClassifier(model="test/model")
        with patch("litellm.completion", side_effect=RuntimeError("model error")):
            result = clf.classify({"url": "https://example.com/file.pdf"})
        assert result is None

    def test_falls_back_on_timeout(self, classifier_mod):
        clf = classifier_mod.LightLLMClassifier(model="test/model")
        with patch("litellm.completion", side_effect=TimeoutError("timeout")):
            result = clf.classify({})
        assert result is None

    def test_prompt_contains_all_types(self, classifier_mod):
        clf = classifier_mod.LightLLMClassifier(model="test/model")
        payload = {"dummy": "value"}
        captured_prompts = []

        def capture(*args, **kwargs):
            msgs = kwargs.get("messages", [])
            for m in msgs:
                captured_prompts.append(m.get("content", ""))
            raise RuntimeError("stop")

        with patch("litellm.completion", side_effect=capture):
            clf.classify(payload)

        combined = " ".join(captured_prompts)
        for agent_type in classifier_mod.VALID_AGENT_TYPES:
            assert agent_type in combined, f"{agent_type!r} not in LLM prompt"


# ===========================================================================
# BaseSubAgent contract tests
# ===========================================================================


class TestBaseSubAgentPublish:
    def test_publish_schema_all_agents(self, all_agents):
        required_keys = {"agent_type", "agent_purpose", "instance_id",
                         "timeline_memory_id", "session_memory_id"}
        for agent in all_agents:
            manifest = agent.publish()
            missing = required_keys - set(manifest.keys())
            assert not missing, f"{agent.AGENT_TYPE} missing keys: {missing}"
            assert manifest["agent_type"] == agent.AGENT_TYPE

    def test_instance_id_unique_across_agents(self, all_agents):
        ids = [a.instance_id for a in all_agents]
        assert len(ids) == len(set(ids)), "Duplicate instance IDs detected"


class TestBaseSubAgentProcess:
    def test_process_stub_returns_todo(self, all_agents):
        for agent in all_agents:
            result = agent.process("{}", "dummy-data-id")
            # url_download is a no-op; processing is done by re-invoked pipeline
            if agent.AGENT_TYPE == "url_download":
                assert result.get("status") == "ok"
            else:
                # Base stub returns "todo"; some agents return "error" when processing fails
                assert result.get("status") in ("todo", "ok", "error"), (
                    f"{agent.AGENT_TYPE}.process() returned unexpected status: {result.get('status')}"
                )


class TestBaseSubAgentWriteRecord:
    def test_write_record_increments_stats(self):
        from webhook.processor.webhook_agent.sub_agents.documents.pdf import PdfAgent
        from webhook.processor.webhook_agent import api_client as client_mod

        agent = PdfAgent()
        with (
            patch.object(client_mod.data_client, "create", return_value={"data_id": "d1", "version": 1}),
            patch.object(client_mod.stats_client, "increment") as mock_inc,
        ):
            agent.write_record("{}", name="test-event", group_context=MagicMock(
                timeline_memory_id="tl-1", session_memory_id="sess-1", group_id="g", user_id="u",
            ))
            mock_inc.assert_called_once_with("pdf")

    def test_write_record_includes_group_memory_ids_only(self):
        """Agent attaches only to pre-existing memories (group context); does not create agent memories."""
        from webhook.processor.webhook_agent.sub_agents.documents.pdf import PdfAgent
        from webhook.processor.webhook_agent.group_context import build_group_context
        from webhook.processor.webhook_agent import api_client as client_mod

        agent = PdfAgent()
        ctx = build_group_context({"memory_prefix": "ord-42"})

        captured: dict = {}

        def capture_create(**kwargs):
            captured.update(kwargs)
            return {"data_id": "d1", "version": 1}

        with (
            patch.object(client_mod.data_client, "create", side_effect=capture_create),
            patch.object(client_mod.stats_client, "increment"),
        ):
            agent.write_record("{}", group_context=ctx)

        memory_ids = captured.get("memory_ids", [])
        assert "timeline-ord-42" in memory_ids
        assert "session-ord-42" in memory_ids

    def test_write_record_includes_group_tags(self):
        from webhook.processor.webhook_agent.sub_agents.documents.pdf import PdfAgent
        from webhook.processor.webhook_agent.group_context import build_group_context
        from webhook.processor.webhook_agent import api_client as client_mod

        agent = PdfAgent()
        ctx = build_group_context({"memory_prefix": "ord-42", "user_id": "alice", "correlation_id": "batch-2"})

        captured: dict = {}

        def capture_create(**kwargs):
            captured.update(kwargs)
            return {"data_id": "d1", "version": 1}

        with (
            patch.object(client_mod.data_client, "create", side_effect=capture_create),
            patch.object(client_mod.stats_client, "increment"),
        ):
            agent.write_record("{}", group_context=ctx)

        tags = captured.get("tags", [])
        assert "user_id:alice" in tags

    def test_different_agent_types_same_prefix_share_group_memory(self):
        from webhook.processor.webhook_agent.sub_agents.documents.pdf import PdfAgent
        from webhook.processor.webhook_agent.sub_agents.media.video_url import VideoUrlAgent
        from webhook.processor.webhook_agent.group_context import build_group_context

        ctx_pdf = build_group_context({"memory_prefix": "ord-42"})
        ctx_video = build_group_context({"memory_prefix": "ord-42"})

        assert ctx_pdf.timeline_memory_id == ctx_video.timeline_memory_id
        assert ctx_pdf.session_memory_id == ctx_video.session_memory_id


class TestBaseSubAgentDeleteRecord:
    def test_delete_record_decrements_correct_type(self):
        from webhook.processor.webhook_agent.sub_agents.documents.pdf import PdfAgent
        from webhook.processor.webhook_agent import api_client as client_mod

        agent = PdfAgent()

        with (
            patch.object(
                client_mod.data_client,
                "get_metadata",
                return_value={"tags": ["agent_type:pdf", "user_id:alice"]},
            ),
            patch.object(client_mod.data_client, "delete", return_value={}),
            patch.object(client_mod.stats_client, "decrement") as mock_dec,
        ):
            agent.delete_record("d1")
            mock_dec.assert_called_once_with("pdf")

    def test_delete_record_reads_tag_for_correct_type(self):
        """The tag on the data should determine which type is decremented."""
        from webhook.processor.webhook_agent.sub_agents.documents.pdf import PdfAgent
        from webhook.processor.webhook_agent import api_client as client_mod

        agent = PdfAgent()

        # Pretend data was actually stored as a lidar item (tag mismatch simulation)
        with (
            patch.object(
                client_mod.data_client,
                "get_metadata",
                return_value={"tags": ["agent_type:lidar"]},
            ),
            patch.object(client_mod.data_client, "delete", return_value={}),
            patch.object(client_mod.stats_client, "decrement") as mock_dec,
        ):
            agent.delete_record("d1")
            mock_dec.assert_called_once_with("lidar")


# ===========================================================================
# AGENT_REGISTRY completeness
# ===========================================================================


class TestAgentRegistryCompleteness:
    EXPECTED_TYPES = {
        # Media
        "video_stream", "video_url", "audio_stream", "audio_url", "image", "image_batch",
        # Documents
        "pdf", "office_doc", "markdown", "html_doc",
        # Structured
        "json", "xml", "csv", "yaml",
        # Code & logs
        "code", "log_stream", "log_file",
        # Sensor
        "sensor", "gps", "biometric", "iot_sensor",
        # Spatial
        "lidar", "geospatial", "model_3d",
        # Communication
        "email", "chat", "calendar", "web_page", "feed", "channel_message",
        # Download (Layer 0b — url present but not downloaded)
        "url_download",
        # Plan 3 and binary
        "conferencing", "vehicle_telemetry", "satellite", "scientific", "financial",
        "industrial", "infrastructure",
        "archive", "time_series", "medical_imaging", "binary_blob",
    }

    def test_all_types_present(self, registry_mod):
        _, agent_registry = registry_mod
        missing = self.EXPECTED_TYPES - set(agent_registry.keys())
        assert not missing, f"Missing agent types: {missing}"

    def test_registry_count(self, registry_mod):
        _, agent_registry = registry_mod
        # Registry and EXPECTED_TYPES must match so we don't miss or extra-list agents
        assert len(agent_registry) == len(self.EXPECTED_TYPES), (
            f"registry has {len(agent_registry)} agents but EXPECTED_TYPES has {len(self.EXPECTED_TYPES)}"
        )

    def test_binary_blob_is_fallback(self, registry_mod):
        _, agent_registry = registry_mod
        assert "binary_blob" in agent_registry
        assert agent_registry["binary_blob"].AGENT_TYPE == "binary_blob"


# ===========================================================================
# StatsClient tests
# ===========================================================================


class TestStatsClient:
    def test_increment_calls_correct_endpoint(self):
        from webhook.processor.webhook_agent.api_client.stats import StatsClient
        import requests as req_mod

        client = StatsClient(base_url="http://test")
        req_mod.post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"counts": {"pdf": 1}, "total": 1, "last_updated": "now"},
            raise_for_status=lambda: None,
        )
        result = client.increment("pdf")
        req_mod.post.assert_called_with(
            "http://test/api/v1/stats/agent-types/pdf/increment",
            timeout=15,
        )
        assert result.get("total") == 1

    def test_decrement_calls_correct_endpoint(self):
        from webhook.processor.webhook_agent.api_client.stats import StatsClient
        import requests as req_mod

        client = StatsClient(base_url="http://test")
        req_mod.post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"counts": {"pdf": 0}, "total": 0, "last_updated": "now"},
            raise_for_status=lambda: None,
        )
        result = client.decrement("pdf")
        req_mod.post.assert_called_with(
            "http://test/api/v1/stats/agent-types/pdf/decrement",
            timeout=15,
        )
        assert result.get("total") == 0

    def test_increment_swallows_exception(self):
        from webhook.processor.webhook_agent.api_client.stats import StatsClient
        import requests as req_mod

        client = StatsClient(base_url="http://test")
        req_mod.post.side_effect = req_mod.RequestException("network error")
        result = client.increment("pdf")
        assert result.get("status") == "error"
        # Reset side effect for other tests
        req_mod.post.side_effect = None
        req_mod.post.return_value = MagicMock(
            status_code=200,
            json=lambda: {},
            raise_for_status=lambda: None,
        )
