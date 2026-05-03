"""ScientificAgent — lab results, spectrometry, and research data (Plan 3)."""

from ..base import BaseSubAgent


class ScientificAgent(BaseSubAgent):
    """Processes scientific data: lab results, spectrometry, microscopy, genomics.

    Handles outputs from scientific instruments and research pipelines including
    mass spectrometry, NMR, gene sequencing (FASTQ/VCF), flow cytometry, and
    general laboratory information management system (LIMS) exports.
    """

    AGENT_TYPE = "scientific"
    AGENT_PURPOSE = "Processes scientific data including lab results, spectrometry, and genomics"
    MIME_PATTERNS = [
        "application/x-scientific",
        "application/x-spectrometry",
        "application/x-genomics",
        "chemical/x-mdl-sdfile",
        "chemical/x-pdb",
        "application/x-fastq",
        "application/x-vcf",
        "application/x-lims",
    ]
    MODEL_TIER = "large"

    def _process(self, payload_json: str, data_id: str, group_context=None, payload_meta=None) -> dict:
        # Text-based scientific formats (FASTQ, VCF, PDB, SDF, LIMS) use the
        # standard text pipeline; binary formats use metadata extraction.
        from ..llm_utils import _SCIENTIFIC_TEXT_MIMES, analyse_binary_metadata_payload, analyse_payload
        mime = (payload_meta or {}).get("mime_type", "")
        if mime in _SCIENTIFIC_TEXT_MIMES:
            return analyse_payload(
                self.AGENT_TYPE, payload_json, data_id, self.instance_id,
                self.AGENT_PURPOSE, group_context, payload_meta,
            )
        return analyse_binary_metadata_payload(
            self.AGENT_TYPE, payload_json, data_id, self.instance_id,
            self.AGENT_PURPOSE, group_context, payload_meta,
        )
