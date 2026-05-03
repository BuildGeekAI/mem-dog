"""ConferencingAgent — Zoom, Google Meet, Teams recordings and transcripts (Plan 3)."""

from ..base import BaseSubAgent


class ConferencingAgent(BaseSubAgent):
    """Processes video-conferencing payloads: meeting recordings, transcripts, chat exports.

    Handles Zoom, Google Meet, Microsoft Teams, and similar platforms.
    """

    AGENT_TYPE = "conferencing"
    AGENT_PURPOSE = "Processes video-conferencing recordings, transcripts, and meeting data"
    MIME_PATTERNS = [
        "application/x-zoom",
        "application/x-google-meet",
        "application/x-teams-meeting",
        "application/x-conferencing",
        "application/x-vnd.zoom",
    ]
    MODEL_TIER = "large"

    def _process(self, payload_json: str, data_id: str, group_context=None, payload_meta=None) -> dict:
        from ..llm_utils import analyse_payload
        return analyse_payload(
            self.AGENT_TYPE, payload_json, data_id, self.instance_id,
            self.AGENT_PURPOSE, group_context, payload_meta,
        )
