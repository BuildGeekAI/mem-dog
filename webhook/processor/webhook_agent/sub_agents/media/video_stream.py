"""VideoStreamAgent — Processes real-time video stream data (RTSP, WebRTC)."""

from ..base import BaseSubAgent


class VideoStreamAgent(BaseSubAgent):
    """Processes real-time video stream data (RTSP, WebRTC)."""

    AGENT_TYPE = "video_stream"
    AGENT_PURPOSE = "Processes real-time video stream data (RTSP, WebRTC)"
    MIME_PATTERNS = ["video/stream", "video/x-stream"]
    MODEL_TIER = "large"

    def _process(self, payload_json: str, data_id: str, group_context=None, payload_meta=None) -> dict:
        from ..llm_utils import analyse_media_payload
        return analyse_media_payload(
            self.AGENT_TYPE, payload_json, data_id,
            self.instance_id, self.AGENT_PURPOSE,
            group_context, payload_meta,
        )
