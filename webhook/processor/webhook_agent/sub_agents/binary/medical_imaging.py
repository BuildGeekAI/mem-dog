"""MedicalImagingAgent — Processes medical imaging data (DICOM)."""

from ..base import BaseSubAgent


class MedicalImagingAgent(BaseSubAgent):
    """Processes medical imaging data in DICOM format."""

    AGENT_TYPE = "medical_imaging"
    AGENT_PURPOSE = "Processes medical imaging data (DICOM)"
    MIME_PATTERNS = ["application/dicom"]
    MODEL_TIER = "large"

    def _process(self, payload_json: str, data_id: str, group_context=None, payload_meta=None) -> dict:
        from ..llm_utils import analyse_binary_metadata_payload
        return analyse_binary_metadata_payload(
            self.AGENT_TYPE, payload_json, data_id,
            self.instance_id, self.AGENT_PURPOSE,
            group_context, payload_meta,
        )
