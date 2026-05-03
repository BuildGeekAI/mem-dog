"""Grafana webhook channel adapter.

Handles Grafana alerting webhook payloads (Unified Alerting).

Reference: https://grafana.com/docs/grafana/latest/alerting/configure-notifications/manage-contact-points/integrations/webhook-notifier/
"""

from __future__ import annotations

from typing import Any

from .base import BaseChannelAdapter, NormalizedMessage


class GrafanaAdapter(BaseChannelAdapter):

    @property
    def channel_type(self) -> str:
        return "grafana"

    async def normalize(self, payload: dict[str, Any]) -> NormalizedMessage:
        title = payload.get("title", "")
        message = payload.get("message", "")
        state = payload.get("state", payload.get("status", ""))
        rule_name = payload.get("ruleName", payload.get("rule_name", ""))
        rule_url = payload.get("ruleUrl", payload.get("rule_url", ""))
        org_id = payload.get("orgId", "")

        # Alerts array (Unified Alerting format)
        alerts = payload.get("alerts", [])

        text_parts = [f"Grafana: {state or 'alert'}"]
        if title:
            text_parts.append(f"Title: {title}")
        if rule_name:
            text_parts.append(f"Rule: {rule_name}")
        if message:
            text_parts.append(message[:500])

        for alert in alerts[:5]:
            if not isinstance(alert, dict):
                continue
            status = alert.get("status", "")
            labels = alert.get("labels", {})
            annotations = alert.get("annotations", {})
            summary = annotations.get("summary", annotations.get("description", ""))
            alertname = labels.get("alertname", "")

            if alertname:
                text_parts.append(f"\nAlert: {alertname} [{status}]")
            if summary:
                text_parts.append(f"  {summary[:200]}")

            # Values
            values = alert.get("values", alert.get("valueString", ""))
            if values:
                text_parts.append(f"  Values: {str(values)[:200]}")

        # Eval matches (legacy format)
        eval_matches = payload.get("evalMatches", [])
        for match in eval_matches[:5]:
            if isinstance(match, dict):
                metric = match.get("metric", "")
                value = match.get("value", "")
                text_parts.append(f"  {metric}: {value}")

        return NormalizedMessage(
            channel_type="grafana",
            channel_id=str(org_id),
            message_id=str(payload.get("id", "")),
            text="\n".join(text_parts),
            source_type="infrastructure",
            raw=payload,
            extra={
                "state": state,
                "rule_name": rule_name,
                "url": rule_url,
                "num_alerts": len(alerts),
            },
        )
