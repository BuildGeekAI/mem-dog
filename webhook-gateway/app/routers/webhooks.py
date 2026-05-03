"""Inbound webhook router — ``POST /webhooks/{identifier}``.

Supports two routing modes:
- ``whk_*`` identifiers: look up the webhook record for user_id + channel_type.
- Legacy channel names (``slack``, ``email``, etc.): resolve user via heuristics.

Dispatches to the appropriate channel adapter, optionally classifies via
Gemini, builds the envelope, and forwards it to the webhook pipeline.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, Response

from .. import config
from ..channel_policy import check_access
from ..channels.base import BaseChannelAdapter
from ..channels.discord import DiscordAdapter
from ..channels.email import EmailAdapter
from ..channels.generic import GenericAdapter
from ..channels.msteams import MSTeamsAdapter
from ..channels.openclaw_bridge import OpenClawBridgeAdapter
from ..channels.slack import SlackAdapter
from ..channels.jira import JiraAdapter
from ..channels.github import GitHubAdapter
from ..channels.twilio import TwilioAdapter
from ..channels.notion import NotionAdapter
from ..channels.linear import LinearAdapter
from ..channels.hubspot import HubSpotAdapter
from ..channels.stripe_adapter import StripeAdapter
from ..channels.asana import AsanaAdapter
from ..channels.salesforce import SalesforceAdapter
from ..channels.pagerduty import PagerDutyAdapter
from ..channels.datadog import DatadogAdapter
from ..channels.sentry import SentryAdapter
from ..channels.grafana import GrafanaAdapter
from ..channels.opsgenie import OpsGenieAdapter
from ..channels.yelp import YelpAdapter
from ..channels.google_business import GoogleBusinessAdapter
from ..channels.trustpilot import TrustpilotAdapter
from ..channels.g2 import G2Adapter
from ..channels.tripadvisor import TripAdvisorAdapter
from ..channels.appstore import AppStoreAdapter
from ..channels.capterra import CapterraAdapter
from ..channels.telegram import TelegramAdapter
from ..channels.video import VideoAdapter
from ..channels.webchat import WebChatAdapter
from ..channels.whatsapp import WhatsAppAdapter
from ..channels.zoom import ZoomAdapter
from ..envelope import build_envelope
from ..forwarder import forward_envelope
from ..credentials import lookup_connections, tag_connection, _load_provider_meta
from ..identity import resolve_user_id
from ..llm import classify_message, summarize_context
from ..memory import publish_to_memory
from ..telemetry import trace_span
from ..webhook_lookup import get_webhook

_log = logging.getLogger("openclaw_gateway.routers.webhooks")

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

_openclaw_bridge = OpenClawBridgeAdapter()

_ADAPTERS: dict[str, BaseChannelAdapter] = {
    "generic": GenericAdapter(),
    "email": EmailAdapter(),
    "video": VideoAdapter(),
    "telegram": TelegramAdapter(),
    "slack": SlackAdapter(),
    "discord": DiscordAdapter(),
    "whatsapp": WhatsAppAdapter(),
    "msteams": MSTeamsAdapter(),
    "webchat": WebChatAdapter(),
    "jira": JiraAdapter(),
    "github": GitHubAdapter(),
    "twilio": TwilioAdapter(),
    "notion": NotionAdapter(),
    "linear": LinearAdapter(),
    "hubspot": HubSpotAdapter(),
    "stripe": StripeAdapter(),
    "asana": AsanaAdapter(),
    "salesforce": SalesforceAdapter(),
    "pagerduty": PagerDutyAdapter(),
    "datadog": DatadogAdapter(),
    "sentry": SentryAdapter(),
    "grafana": GrafanaAdapter(),
    "opsgenie": OpsGenieAdapter(),
    "yelp": YelpAdapter(),
    "google-business": GoogleBusinessAdapter(),
    "trustpilot": TrustpilotAdapter(),
    "g2": G2Adapter(),
    "tripadvisor": TripAdvisorAdapter(),
    "appstore": AppStoreAdapter(),
    "capterra": CapterraAdapter(),
    "zoom": ZoomAdapter(),
    "openclaw": _openclaw_bridge,
    # OpenClaw bridge channels — all route through the OpenClaw bridge adapter
    "signal": _openclaw_bridge,
    "matrix": _openclaw_bridge,
    "irc": _openclaw_bridge,
    "googlechat": _openclaw_bridge,
    "line": _openclaw_bridge,
    "feishu": _openclaw_bridge,
    "mattermost": _openclaw_bridge,
    "nextcloud-talk": _openclaw_bridge,
    "nostr": _openclaw_bridge,
    "tlon": _openclaw_bridge,
    "twitch": _openclaw_bridge,
    "zalo": _openclaw_bridge,
    "bluebubbles": _openclaw_bridge,
    "imessage": _openclaw_bridge,
    "synology-chat": _openclaw_bridge,
}


@router.post("/{identifier}")
async def receive_webhook(
    identifier: str,
    request: Request,
    pipeline: str | None = Query(None, description="Pipeline routing: 'gke' for GKE path"),
) -> dict[str, Any]:
    """Receive an inbound webhook and forward it.

    Supports two routing modes:
    - **New path:** ``identifier`` starts with ``whk_`` — look up the webhook
      record to get user_id and channel_type directly.
    - **Legacy path:** ``identifier`` is a channel type name (e.g. ``slack``,
      ``email``) — resolve user identity via heuristic lookup.
    """
    webhook_record: dict[str, Any] | None = None
    resolved_uid: str | None = None

    if identifier.startswith("whk_"):
        # New path: webhook_id-based routing
        webhook_record = await get_webhook(identifier)
        if webhook_record is None:
            raise HTTPException(status_code=404, detail=f"Webhook not found: {identifier}")
        if webhook_record.get("status") != "active":
            raise HTTPException(
                status_code=410,
                detail=f"Webhook is {webhook_record.get('status', 'inactive')}",
            )
        channel_type = webhook_record["channel_type"]
        resolved_uid = webhook_record["user_id"]
    elif identifier in _ADAPTERS:
        # Legacy path: channel_type-based routing
        channel_type = identifier
    else:
        raise HTTPException(status_code=404, detail=f"Unknown webhook endpoint: {identifier}")

    adapter = _ADAPTERS.get(channel_type)
    if adapter is None:
        raise HTTPException(status_code=400, detail=f"Unsupported channel type: {channel_type}")

    body = await request.body()
    if len(body) > config.MAX_PAYLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Payload too large")
    if not body:
        raise HTTPException(status_code=400, detail="Empty request body")

    try:
        payload: dict[str, Any] = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Payload must be a JSON object")

    with trace_span(
        f"webhooks.{channel_type}",
        attributes={"channel_type": channel_type, "payload_size": len(body)},
    ) as span_ctx:
        adapter.validate(payload, headers=dict(request.headers))

        msg = await adapter.normalize(payload)

        # Slack url_verification challenge -- echo it back immediately
        if channel_type == "slack" and msg.extra.get("challenge"):
            return {"challenge": msg.extra["challenge"]}

        # Zoom CRC endpoint URL validation -- return challenge response
        if channel_type == "zoom" and msg.extra.get("zoom_crc"):
            return msg.extra["zoom_crc"]

        peer_id = msg.peer_id or msg.user_id or ""

        denial = check_access(channel_type, peer_id)
        if denial:
            _log.warning("Access denied: %s (peer=%s)", denial, peer_id)
            raise HTTPException(status_code=403, detail=denial)

        if resolved_uid is None:
            # Legacy path only — new-path already has user_id from webhook record
            resolved_uid = await resolve_user_id(channel_type, peer_id)

        # Look up ALL active integration connections for this user and tag them
        integration_refs: list[dict[str, Any]] | None = None
        try:
            connections = await lookup_connections(resolved_uid)
            if connections:
                provider_meta = _load_provider_meta()
                integration_refs = [
                    tag_connection(c, channel_type, provider_meta)
                    for c in connections
                ]
        except Exception as exc:
            _log.debug("Integration lookup failed for %s: %s", resolved_uid, exc)

        llm_result: dict[str, Any] | None = None
        if msg.text and config.has_llm_configured():
            if channel_type in ("video", "zoom"):
                summary = await summarize_context(msg.text)
                if summary:
                    llm_result = {"summary": summary}
            else:
                llm_result = await classify_message(msg.text)

        envelope = build_envelope(
            msg,
            resolved_user_id=resolved_uid,
            llm_classification=llm_result,
            integrations=integration_refs,
            webhook_id=identifier if webhook_record else None,
        )

        result = await forward_envelope(envelope, pipeline=pipeline)

        # Download and ingest attachments (Slack files need bot token)
        if msg.attachments:
            from ..attachment_downloader import download_and_ingest_attachments
            background_tasks = request.state._state.get("background_tasks")
            asyncio.ensure_future(
                download_and_ingest_attachments(
                    attachments=msg.attachments,
                    channel_type=channel_type,
                    user_id=resolved_uid or "",
                    pipeline=pipeline,
                )
            )

        trace_id = envelope["_envelope_meta"]["trace_id"]

        data_id = None
        if config.PUBLISH_TO_MEMORY:
            data_id = await publish_to_memory(
                msg,
                resolved_user_id=resolved_uid,
                trace_id=trace_id,
                llm_classification=llm_result,
            )

        span_ctx["user_id"] = resolved_uid

    if not result.success:
        _log.error("Forward failed for %s webhook: %s", channel_type, result.error)
        raise HTTPException(status_code=502, detail=f"Forwarding failed: {result.error}")

    response: dict[str, Any] = {
        "status": "accepted",
        "channel_type": channel_type,
        "message_id": result.message_id,
        "trace_id": trace_id,
        "forwarded_at": datetime.now(timezone.utc).isoformat(),
    }
    if data_id:
        response["data_id"] = data_id
    if webhook_record:
        response["webhook_id"] = identifier
    return response
