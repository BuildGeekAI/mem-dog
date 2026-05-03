"""PdfAgent — Processes PDF documents."""

from ..base import BaseSubAgent


class PdfAgent(BaseSubAgent):
    """Processes PDF documents."""

    AGENT_TYPE = "pdf"
    AGENT_PURPOSE = "Processes PDF documents"
    MIME_PATTERNS = ["application/pdf", "application/x-pdf"]
    MODEL_TIER = "large"

    def _process(self, payload_json: str, data_id: str, group_context=None, payload_meta=None) -> dict:
        from ..llm_utils import analyse_document_payload
        return analyse_document_payload(
            self.AGENT_TYPE, payload_json, data_id,
            self.instance_id, self.AGENT_PURPOSE,
            group_context, payload_meta,
        )
