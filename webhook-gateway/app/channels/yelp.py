"""Yelp review channel adapter.

Handles Yelp review data pushed via a polling bridge or manual import.
Yelp doesn't have native webhooks — data arrives via a polling service
or direct API import.

Reference: https://docs.developer.yelp.com/docs/fusion-intro
"""

from __future__ import annotations

from typing import Any

from .base import BaseChannelAdapter, NormalizedMessage


class YelpAdapter(BaseChannelAdapter):

    @property
    def channel_type(self) -> str:
        return "yelp"

    async def normalize(self, payload: dict[str, Any]) -> NormalizedMessage:
        # Single review format
        review = payload.get("review", payload)
        business = payload.get("business", {})

        reviewer = review.get("user", {})
        reviewer_name = reviewer.get("name", "") if isinstance(reviewer, dict) else str(reviewer)
        rating = review.get("rating", "")
        text = review.get("text", "")
        time_created = review.get("time_created", "")
        review_url = review.get("url", "")

        business_name = business.get("name", payload.get("business_name", ""))
        business_id = business.get("id", payload.get("business_id", ""))
        categories = business.get("categories", [])
        category_names = [c.get("title", "") for c in categories if isinstance(c, dict)]

        text_parts = [f"Yelp Review: {'★' * int(rating)}{' ☆' * (5 - int(rating))}" if rating else "Yelp Review"]
        if business_name:
            text_parts.append(f"Business: {business_name}")
        if reviewer_name:
            text_parts.append(f"By: {reviewer_name}")
        if time_created:
            text_parts.append(f"Date: {time_created}")
        if category_names:
            text_parts.append(f"Categories: {', '.join(category_names)}")
        if text:
            text_parts.append(f"\n{text}")

        return NormalizedMessage(
            channel_type="yelp",
            channel_id=business_id,
            peer_id=reviewer_name,
            message_id=review.get("id", ""),
            text="\n".join(text_parts),
            source_type="other",
            raw=payload,
            extra={
                "rating": rating,
                "business_name": business_name,
                "business_id": business_id,
                "review_url": review_url,
                "categories": category_names,
            },
        )
