"""Model3dAgent — Processes 3D model data."""

from ..base import BaseSubAgent


class Model3dAgent(BaseSubAgent):
    """Processes 3D model data (GLTF, OBJ, STL)."""

    AGENT_TYPE = "model_3d"
    AGENT_PURPOSE = "Processes 3D model data (GLTF, OBJ, STL)"
    MIME_PATTERNS = ["model/gltf+json", "model/gltf-binary", "model/"]
    MODEL_TIER = "large"

    def _process(self, payload_json: str, data_id: str, group_context=None, payload_meta=None) -> dict:
        from ..llm_utils import analyse_binary_metadata_payload
        return analyse_binary_metadata_payload(
            self.AGENT_TYPE, payload_json, data_id,
            self.instance_id, self.AGENT_PURPOSE,
            group_context, payload_meta,
        )
