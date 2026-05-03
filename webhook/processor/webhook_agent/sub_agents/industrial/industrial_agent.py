"""IndustrialAgent — SCADA, PLC, and factory-floor data (Plan 3)."""

from ..base import BaseSubAgent


class IndustrialAgent(BaseSubAgent):
    """Processes industrial control system data: SCADA, PLC, OPC-UA, MQTT factory topics.

    Handles time-series process values, alarm logs, equipment events, and
    manufacturing execution system (MES) outputs.
    """

    AGENT_TYPE = "industrial"
    AGENT_PURPOSE = "Processes industrial data including SCADA, PLC, and factory-floor telemetry"
    MIME_PATTERNS = [
        "application/x-industrial",
        "application/x-scada",
        "application/x-opc-ua",
        "application/x-plc",
        "application/x-mes",
        "application/x-mqtt-industrial",
    ]
    MODEL_TIER = "medium"

    def _process(self, payload_json: str, data_id: str, group_context=None, payload_meta=None) -> dict:
        from ..llm_utils import analyse_payload
        return analyse_payload(
            self.AGENT_TYPE, payload_json, data_id, self.instance_id,
            self.AGENT_PURPOSE, group_context, payload_meta,
        )
