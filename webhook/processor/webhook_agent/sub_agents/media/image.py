"""ImageAgent — Processes single image data."""

from ..base import BaseSubAgent


class ImageAgent(BaseSubAgent):
    """Processes single image data (.jpg, .png, .gif, .webp, .svg)."""

    AGENT_TYPE = "image"
    AGENT_PURPOSE = "Processes single image data"
    MIME_PATTERNS = ["image/jpeg", "image/png", "image/gif", "image/webp", "image/svg+xml", "image/"]
    MODEL_TIER = "large"

    def _process(self, payload_json: str, data_id: str, group_context=None, payload_meta=None) -> dict:
        from ..llm_utils import analyse_media_payload
        return analyse_media_payload(
            self.AGENT_TYPE, payload_json, data_id,
            self.instance_id, self.AGENT_PURPOSE,
            group_context, payload_meta,
        )
