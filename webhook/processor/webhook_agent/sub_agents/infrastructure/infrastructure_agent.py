"""InfrastructureAgent — Kubernetes events, cloud logs, and DevOps data (Plan 3)."""

from ..base import BaseSubAgent


class InfrastructureAgent(BaseSubAgent):
    """Processes cloud/infrastructure events: Kubernetes events, CloudWatch logs, GCP logs.

    Handles structured log streams, deployment events, alerting payloads
    (PagerDuty, Opsgenie), and CI/CD pipeline results.
    """

    AGENT_TYPE = "infrastructure"
    AGENT_PURPOSE = "Processes cloud/infrastructure events including Kubernetes, logs, and CI/CD data"
    MIME_PATTERNS = [
        "application/x-infrastructure",
        "application/x-k8s-event",
        "application/x-cloudwatch",
        "application/x-gcp-log",
        "application/x-pagerduty",
        "application/x-cicd",
    ]
    MODEL_TIER = "medium"

    def _process(self, payload_json: str, data_id: str, group_context=None, payload_meta=None) -> dict:
        from ..llm_utils import analyse_payload
        return analyse_payload(
            self.AGENT_TYPE, payload_json, data_id, self.instance_id,
            self.AGENT_PURPOSE, group_context, payload_meta,
        )
