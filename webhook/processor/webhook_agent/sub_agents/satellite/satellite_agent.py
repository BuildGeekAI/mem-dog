"""SatelliteAgent — SAR, optical, and hyperspectral satellite imagery (Plan 3)."""

from ..base import BaseSubAgent


class SatelliteAgent(BaseSubAgent):
    """Processes satellite and aerial imagery data.

    Handles metadata and payloads from SAR (synthetic aperture radar),
    multispectral / hyperspectral sensors, and raw scene catalogues from
    platforms such as Sentinel, Landsat, Planet, and Maxar.
    """

    AGENT_TYPE = "satellite"
    AGENT_PURPOSE = "Processes satellite imagery metadata, SAR data, and scene catalogues"
    MIME_PATTERNS = [
        "application/x-satellite",
        "application/x-sar",
        "application/x-geotiff",
        "image/tiff",
        "application/x-hdf5",
        "application/x-netcdf",
        "application/vnd.stac",
    ]
    MODEL_TIER = "large"

    def _process(self, payload_json: str, data_id: str, group_context=None, payload_meta=None) -> dict:
        from ..llm_utils import analyse_binary_metadata_payload
        return analyse_binary_metadata_payload(
            self.AGENT_TYPE, payload_json, data_id, self.instance_id,
            self.AGENT_PURPOSE, group_context, payload_meta,
        )
