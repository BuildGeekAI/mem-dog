"""OfficeDocAgent — Processes Microsoft Office documents."""

from ..base import BaseSubAgent


class OfficeDocAgent(BaseSubAgent):
    """Processes Microsoft Office documents (Word, Excel, PowerPoint)."""

    AGENT_TYPE = "office_doc"
    AGENT_PURPOSE = "Processes Microsoft Office documents (Word, Excel, PowerPoint)"
    MIME_PATTERNS = [
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/msword",
        "application/vnd.ms-excel",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.",
    ]
    MODEL_TIER = "large"

    def _process(self, payload_json: str, data_id: str, group_context=None, payload_meta=None) -> dict:
        from ..llm_utils import analyse_document_payload
        return analyse_document_payload(
            self.AGENT_TYPE, payload_json, data_id,
            self.instance_id, self.AGENT_PURPOSE,
            group_context, payload_meta,
        )
