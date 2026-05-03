"""AudioStreamAgent — Processes real-time audio stream data."""

from ..base import BaseSubAgent


class AudioStreamAgent(BaseSubAgent):
    """Processes real-time audio stream data (WebRTC, streaming audio)."""

    AGENT_TYPE = "audio_stream"
    AGENT_PURPOSE = "Processes real-time audio stream data"
    MIME_PATTERNS = ["audio/stream", "audio/x-stream"]
    MODEL_TIER = "large"

    def _process(self, payload_json: str, data_id: str, group_context=None, payload_meta=None) -> dict:
        from ..llm_utils import analyse_media_payload
        return analyse_media_payload(
            self.AGENT_TYPE, payload_json, data_id,
            self.instance_id, self.AGENT_PURPOSE,
            group_context, payload_meta,
        )
