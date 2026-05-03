"""AudioUrlAgent — Processes audio content from remote URLs."""

from ..base import BaseSubAgent


class AudioUrlAgent(BaseSubAgent):
    """Processes audio content from remote URLs (.mp3, .wav, .flac, .ogg)."""

    AGENT_TYPE = "audio_url"
    AGENT_PURPOSE = "Processes audio content from remote URLs"
    MIME_PATTERNS = ["audio/mpeg", "audio/wav", "audio/flac", "audio/ogg", "audio/"]
    MODEL_TIER = "large"

    def _process(self, payload_json: str, data_id: str, group_context=None, payload_meta=None) -> dict:
        from ..llm_utils import analyse_media_payload
        return analyse_media_payload(
            self.AGENT_TYPE, payload_json, data_id,
            self.instance_id, self.AGENT_PURPOSE,
            group_context, payload_meta,
        )
