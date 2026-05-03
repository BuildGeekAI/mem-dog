"""VehicleTelemetryAgent — CAN bus, OBD-II, and vehicle telematics (Plan 3)."""

from ..base import BaseSubAgent


class VehicleTelemetryAgent(BaseSubAgent):
    """Processes vehicle telemetry: CAN bus frames, OBD-II data, GPS tracks, ECU logs.

    Handles data from connected vehicles, automotive APIs, and IoT fleet management
    systems (Geotab, Samsara, Azuga, etc.).
    """

    AGENT_TYPE = "vehicle_telemetry"
    AGENT_PURPOSE = "Processes vehicle telemetry including CAN bus, OBD-II, and fleet data"
    MIME_PATTERNS = [
        "application/x-vehicle-telemetry",
        "application/x-can-bus",
        "application/x-obd2",
        "application/x-fleet-data",
        "application/vnd.peak-system.can",
    ]
    MODEL_TIER = "medium"

    def _process(self, payload_json: str, data_id: str, group_context=None, payload_meta=None) -> dict:
        from ..llm_utils import analyse_payload
        return analyse_payload(
            self.AGENT_TYPE, payload_json, data_id, self.instance_id,
            self.AGENT_PURPOSE, group_context, payload_meta,
        )
