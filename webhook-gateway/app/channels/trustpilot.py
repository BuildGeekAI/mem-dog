"""Trustpilot webhook channel adapter.

Reference: https://developers.trustpilot.com/webhooks
"""

from __future__ import annotations

from typing import Any

from .base import BaseChannelAdapter, NormalizedMessage


class TrustpilotAdapter(BaseChannelAdapter):

    @property
    def channel_type(self) -> str:
        return "trustpilot"

    async def normalize(self, payload: dict[str, Any]) -> NormalizedMessage:
        event_type = payload.get("eventType", payload.get("type", ""))
        data = payload.get("data", payload)

        review = data if "stars" in data else data.get("review", {})
        stars = review.get("stars", review.get("rating", ""))
        title = review.get("title", "")
        text = review.get("text", review.get("body", ""))
        consumer = review.get("consumer", {})
        consumer_name = consumer.get("displayName", "") if isinstance(consumer, dict) else ""
        created_at = review.get("createdAt", review.get("created_at", ""))
        business_unit = review.get("businessUnit", data.get("businessUnit", {}))
        business_name = business_unit.get("displayName", business_unit.get("name", "")) if isinstance(business_unit, dict) else ""

        text_parts = [f"Trustpilot: {event_type or 'review'}"]
        if stars:
            text_parts.append(f"Rating: {'★' * int(stars)}{'☆' * (5 - int(stars))}")
        if business_name:
            text_parts.append(f"Business: {business_name}")
        if consumer_name:
            text_parts.append(f"By: {consumer_name}")
        if title:
            text_parts.append(f"Title: {title}")
        if text:
            text_parts.append(f"\n{text}")

        return NormalizedMessage(
            channel_type="trustpilot",
            channel_id=business_name,
            peer_id=consumer_name,
            message_id=review.get("id", ""),
            text="\n".join(text_parts),
            source_type="other",
            raw=payload,
            extra={
                "event_type": event_type,
                "stars": stars,
                "business": business_name,
            },
        )
