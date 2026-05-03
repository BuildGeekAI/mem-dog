"""LidarAgent — Processes LiDAR point cloud and spatial scan data."""

from ..base import BaseSubAgent


class LidarAgent(BaseSubAgent):
    """Processes LiDAR point cloud and spatial scan data (.pcd, .las)."""

    AGENT_TYPE = "lidar"
    AGENT_PURPOSE = "Processes LiDAR point cloud and spatial scan data"
    MIME_PATTERNS = ["application/x-lidar", "application/x-pointcloud"]
    MODEL_TIER = "large"

    def _process(self, payload_json: str, data_id: str, group_context=None, payload_meta=None) -> dict:
        from ..llm_utils import analyse_binary_metadata_payload
        return analyse_binary_metadata_payload(
            self.AGENT_TYPE, payload_json, data_id,
            self.instance_id, self.AGENT_PURPOSE,
            group_context, payload_meta,
        )
