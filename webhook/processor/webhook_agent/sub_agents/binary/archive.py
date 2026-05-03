"""ArchiveAgent — Processes compressed archives."""

from ..base import BaseSubAgent


class ArchiveAgent(BaseSubAgent):
    """Processes compressed archives (ZIP, tar, gz, bzip2)."""

    AGENT_TYPE = "archive"
    AGENT_PURPOSE = "Processes compressed archives (ZIP, tar, gz)"
    MIME_PATTERNS = [
        "application/zip",
        "application/x-tar",
        "application/gzip",
        "application/x-bzip2",
    ]
    MODEL_TIER = "small"

    def _process(self, payload_json: str, data_id: str, group_context=None, payload_meta=None) -> dict:
        """Analyse archive manifest / metadata using Gemma 3 1B.

        Args:
            payload_json: The raw webhook payload as a JSON string.
            data_id: mem-dog data ID returned by ``write_record()``.
            group_context: Optional group context forwarded from the router.
            payload_meta: Optional dict with ``detection_layer`` and
                ``mime_type`` from the router.

        Returns:
            Result dict with ``status``, ``data_id``, ``staged_uri``,
            ``analysis``, ``viewpoint``, ``embedding``, and ``metadata``.
        """
        from ..llm_utils import analyse_binary_metadata_payload
        return analyse_binary_metadata_payload(self.AGENT_TYPE, payload_json, data_id, self.instance_id, self.AGENT_PURPOSE, group_context, payload_meta)
