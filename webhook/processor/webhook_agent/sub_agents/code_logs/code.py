"""CodeAgent — Processes source code files, diffs, and notebooks."""

from ..base import BaseSubAgent


class CodeAgent(BaseSubAgent):
    """Processes source code files, diffs, and Jupyter notebooks."""

    AGENT_TYPE = "code"
    AGENT_PURPOSE = "Processes source code files, diffs, and notebooks"
    MIME_PATTERNS = [
        "text/x-python",
        "text/x-typescript",
        "text/x-javascript",
        "text/x-go",
        "application/x-ipynb+json",
        "text/x-",
    ]

    def _process(self, payload_json: str, data_id: str, group_context=None, payload_meta=None) -> dict:
        """Download and analyse source code using Gemma 3 1B.

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
        from ..llm_utils import analyse_payload
        return analyse_payload(self.AGENT_TYPE, payload_json, data_id, self.instance_id, self.AGENT_PURPOSE, group_context, payload_meta)
