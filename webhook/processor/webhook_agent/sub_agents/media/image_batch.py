"""ImageBatchAgent — Processes batches of images."""

from ..base import BaseSubAgent


class ImageBatchAgent(BaseSubAgent):
    """Processes batches of images (arrays of URLs or base64 blobs)."""

    AGENT_TYPE = "image_batch"
    AGENT_PURPOSE = "Processes batches of images (arrays of URLs or base64 blobs)"
    MIME_PATTERNS = ["image/batch", "application/x-image-batch"]
    MODEL_TIER = "large"

    def _process(self, payload_json: str, data_id: str, group_context=None, payload_meta=None) -> dict:
        from ..llm_utils import analyse_media_payload
        return analyse_media_payload(
            self.AGENT_TYPE, payload_json, data_id,
            self.instance_id, self.AGENT_PURPOSE,
            group_context, payload_meta,
        )
