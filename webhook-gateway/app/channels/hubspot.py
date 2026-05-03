"""HubSpot webhook channel adapter.

Handles HubSpot CRM webhook payloads for contact, deal, company,
and ticket events.

Reference: https://developers.hubspot.com/docs/api/webhooks
"""

from __future__ import annotations

from typing import Any

from .base import BaseChannelAdapter, NormalizedMessage


class HubSpotAdapter(BaseChannelAdapter):

    @property
    def channel_type(self) -> str:
        return "hubspot"

    async def normalize(self, payload: dict[str, Any]) -> NormalizedMessage:
        # HubSpot sends an array of events
        events = payload if isinstance(payload, list) else [payload]
        event = events[0] if events else {}

        event_type = event.get("subscriptionType", "")
        object_id = str(event.get("objectId", ""))
        change_source = event.get("changeSource", "")
        property_name = event.get("propertyName", "")
        property_value = event.get("propertyValue", "")

        text_parts = [f"HubSpot: {event_type}"]
        text_parts.append(f"Object ID: {object_id}")
        if property_name:
            text_parts.append(f"Changed: {property_name} = {property_value}")

        # Include all events if batch
        if len(events) > 1:
            text_parts.append(f"\n{len(events)} changes in batch:")
            for e in events[1:5]:
                prop = e.get("propertyName", "")
                val = e.get("propertyValue", "")
                if prop:
                    text_parts.append(f"  {prop} = {val}")

        return NormalizedMessage(
            channel_type="hubspot",
            channel_id=event_type.split(".")[0] if "." in event_type else "",
            message_id=str(event.get("eventId", object_id)),
            user_id=str(event.get("appId", "")),
            text="\n".join(text_parts),
            source_type="other",
            raw=payload if isinstance(payload, dict) else {"events": payload},
            extra={
                "event_type": event_type,
                "object_id": object_id,
                "change_source": change_source,
                "property_name": property_name,
            },
        )
