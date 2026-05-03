"""BinaryBlobAgent — Catch-all for unknown or raw binary data.

This agent handles any payload that could not be matched by any other
agent.  No data is ever dropped — it lands here as a fallback.
"""

from ..base import BaseSubAgent


class BinaryBlobAgent(BaseSubAgent):
    """Catch-all for unknown or raw binary data.

    Used as the final fallback in the routing chain.  Ensures that every
    payload is stored even if its type cannot be determined.
    """

    AGENT_TYPE = "binary_blob"
    AGENT_PURPOSE = "Catch-all for unknown or raw binary data"
    MIME_PATTERNS = ["application/octet-stream"]
    MODEL_TIER = "small"

    def _process(self, payload_json: str, data_id: str, group_context=None, payload_meta=None) -> dict:
        from ..llm_utils import analyse_payload
        return analyse_payload(
            self.AGENT_TYPE, payload_json, data_id,
            self.instance_id, self.AGENT_PURPOSE,
            group_context, payload_meta,
        )
