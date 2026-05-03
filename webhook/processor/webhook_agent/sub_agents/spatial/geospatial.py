"""GeospatialAgent — Processes geospatial data."""

from ..base import BaseSubAgent


class GeospatialAgent(BaseSubAgent):
    """Processes geospatial data (GeoJSON, KML, shapefiles)."""

    AGENT_TYPE = "geospatial"
    AGENT_PURPOSE = "Processes geospatial data (GeoJSON, KML, shapefiles)"
    MIME_PATTERNS = [
        "application/geo+json",
        "application/vnd.google-earth.kml+xml",
        "application/x-shapefile",
    ]
    MODEL_TIER = "large"

    def _process(self, payload_json: str, data_id: str, group_context=None, payload_meta=None) -> dict:
        """Analyse geospatial data using Gemma 3 1B.

        Args:
            payload_json: The raw webhook payload as a JSON string.
            data_id: memdog data ID returned by ``write_record()``.
            group_context: Optional group context forwarded from the router.
            payload_meta: Optional dict with ``detection_layer`` and
                ``mime_type`` from the router.

        Returns:
            Result dict with ``status``, ``data_id``, ``staged_uri``,
            ``analysis``, ``viewpoint``, ``embedding``, and ``metadata``.
        """
        from ..llm_utils import analyse_payload
        return analyse_payload(self.AGENT_TYPE, payload_json, data_id, self.instance_id, self.AGENT_PURPOSE, group_context, payload_meta)
