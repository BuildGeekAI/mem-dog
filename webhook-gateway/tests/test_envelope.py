"""Unit tests for the envelope builder."""

from __future__ import annotations

from app.channels.base import NormalizedMessage
from app.envelope import build_envelope


class TestBuildEnvelope:
    def _make_msg(self, **overrides):
        defaults = {
            "channel_type": "email",
            "text": "Hello",
            "peer_id": "sender@test.com",
            "source_type": "email",
        }
        defaults.update(overrides)
        return NormalizedMessage(**defaults)

    def test_basic_structure(self):
        env = build_envelope(self._make_msg())
        assert "data" in env
        assert "meta_data" in env
        assert "_envelope_meta" in env

    def test_trace_ids_present(self):
        env = build_envelope(self._make_msg())
        meta = env["_envelope_meta"]
        assert len(meta["trace_id"]) == 32
        assert len(meta["span_id"]) == 16
        assert meta["gateway"] == "webhook-gateway"
        assert meta["channel_type"] == "email"

    def test_trace_context_in_meta_data(self):
        env = build_envelope(self._make_msg())
        ctx = env["meta_data"]["__trace_context__"]
        assert ctx["trace_id"] == env["_envelope_meta"]["trace_id"]
        assert ctx["span_id"] == env["_envelope_meta"]["span_id"]

    def test_user_id_propagation(self):
        env = build_envelope(self._make_msg(), resolved_user_id="user-42")
        assert env["meta_data"]["identity"]["user_id"] == "user-42"
        assert env["meta_data"]["identity"]["owner"]["user"]["user_id"] == "user-42"

    def test_source_type(self):
        env = build_envelope(self._make_msg(source_type="conferencing"))
        assert env["meta_data"]["content"]["source_type"] == "conferencing"

    def test_channel_message_included(self):
        env = build_envelope(self._make_msg(text="Hello world"))
        cm = env["meta_data"]["content"]["channel_message"]
        assert cm["text"] == "Hello world"
        assert cm["channel_type"] == "email"

    def test_llm_classification_not_in_meta(self):
        """llm_classification is a removed field — should not be in meta_data."""
        classification = {"intent": "action_required", "confidence": 0.9}
        env = build_envelope(self._make_msg(), llm_classification=classification)
        assert "llm_classification" not in env["meta_data"]

    def test_participants_not_in_meta(self):
        """participants is a removed field — should not be in meta_data."""
        env = build_envelope(self._make_msg(participants=["alice", "bob"]))
        assert "participants" not in env["meta_data"]

    def test_raw_data_preserved(self):
        raw = {"custom_field": "value", "text": "original"}
        env = build_envelope(self._make_msg(raw=raw))
        assert env["data"]["payload"]["custom_field"] == "value"

    def test_no_user_id_when_none(self):
        env = build_envelope(self._make_msg(user_id=None))
        assert "user_id" not in env["meta_data"].get("identity", {})
