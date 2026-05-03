"""IotSensorAgent — generic IoT / sensor telemetry (Plan 3).

Handles UDE source_type=sensor and source_type=telemetry payloads that
do not map to a more specific agent (biometric, GPS).
"""

from ..base import BaseSubAgent


class IotSensorAgent(BaseSubAgent):
    """Processes generic IoT sensor and device telemetry payloads.

    Covers temperature/humidity sensors, accelerometers, power meters,
    environmental monitors, and other device telemetry streams not handled
    by the specialised GPS or biometric agents.
    """

    AGENT_TYPE = "iot_sensor"
    AGENT_PURPOSE = "Processes generic IoT sensor and device telemetry"
    MIME_PATTERNS = [
        "application/x-iot-sensor",
        "application/x-device-telemetry",
        "application/x-sensor-data",
        "application/x-mqtt-sensor",
    ]
    MODEL_TIER = "small"

    def _process(self, payload_json: str, data_id: str, group_context=None, payload_meta=None) -> dict:
        from ..llm_utils import analyse_payload
        return analyse_payload(
            self.AGENT_TYPE, payload_json, data_id, self.instance_id,
            self.AGENT_PURPOSE, group_context, payload_meta,
        )
