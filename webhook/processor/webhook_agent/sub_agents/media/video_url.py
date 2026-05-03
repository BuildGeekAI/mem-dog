"""VideoUrlAgent — Processes video content from remote URLs."""

from ..base import BaseSubAgent


class VideoUrlAgent(BaseSubAgent):
    """Processes video content from remote URLs (.mp4, .mov, .avi, .mkv)."""

    AGENT_TYPE = "video_url"
    AGENT_PURPOSE = "Processes video content from remote URLs"
    MIME_PATTERNS = ["video/mp4", "video/quicktime", "video/x-msvideo", "video/x-matroska", "video/"]
    MODEL_TIER = "large"

    def _process(self, payload_json: str, data_id: str, group_context=None, payload_meta=None) -> dict:
        from ..llm_utils import analyse_media_payload
        return analyse_media_payload(
            self.AGENT_TYPE, payload_json, data_id,
            self.instance_id, self.AGENT_PURPOSE,
            group_context, payload_meta,
        )
