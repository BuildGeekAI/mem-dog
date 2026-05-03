"""Salesforce webhook channel adapter.

Handles Salesforce Platform Event and Outbound Message payloads
for lead, opportunity, case, and account events.

Reference: https://developer.salesforce.com/docs/atlas.en-us.api_streaming.meta/api_streaming
"""

from __future__ import annotations

from typing import Any

from .base import BaseChannelAdapter, NormalizedMessage


class SalesforceAdapter(BaseChannelAdapter):

    @property
    def channel_type(self) -> str:
        return "salesforce"

    async def normalize(self, payload: dict[str, Any]) -> NormalizedMessage:
        # Platform Event format
        event_type = payload.get("event", {}).get("type", "") if isinstance(payload.get("event"), dict) else ""
        data = payload.get("data", payload.get("sobject", payload))

        # Outbound Message format (SOAP/REST)
        if "sobject" in payload:
            data = payload["sobject"]

        object_type = data.get("attributes", {}).get("type", "") if isinstance(data.get("attributes"), dict) else data.get("type", "")
        record_id = data.get("Id", data.get("id", ""))

        text_parts = [f"Salesforce: {object_type} {event_type or 'update'}"]

        # Common fields
        name = data.get("Name", data.get("Subject", data.get("Title", "")))
        if name:
            text_parts.append(f"Name: {name}")

        # Lead/Contact
        email = data.get("Email", "")
        company = data.get("Company", data.get("Account", {}).get("Name", "") if isinstance(data.get("Account"), dict) else "")
        if email:
            text_parts.append(f"Email: {email}")
        if company:
            text_parts.append(f"Company: {company}")

        # Opportunity
        stage = data.get("StageName", "")
        amount = data.get("Amount", "")
        if stage:
            text_parts.append(f"Stage: {stage}")
        if amount:
            text_parts.append(f"Amount: ${amount}")

        # Case
        status = data.get("Status", "")
        priority = data.get("Priority", "")
        if status:
            text_parts.append(f"Status: {status}")
        if priority:
            text_parts.append(f"Priority: {priority}")

        # Description
        description = data.get("Description", data.get("Body", ""))
        if description:
            text_parts.append(f"\n{str(description)[:1000]}")

        # Owner
        owner = data.get("OwnerId", data.get("Owner", {}).get("Name", "") if isinstance(data.get("Owner"), dict) else "")

        return NormalizedMessage(
            channel_type="salesforce",
            channel_id=object_type,
            peer_id=str(owner),
            message_id=record_id,
            user_id=data.get("CreatedById", data.get("LastModifiedById", "")),
            text="\n".join(text_parts),
            source_type="other",
            raw=payload,
            extra={
                "object_type": object_type,
                "record_id": record_id,
                "event_type": event_type,
            },
        )
