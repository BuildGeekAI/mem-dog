"""Google Business Profile (GMB) review channel adapter.

Handles Google Business review data.

Reference: https://developers.google.com/my-business/reference/rest
"""

from __future__ import annotations

from typing import Any

from .base import BaseChannelAdapter, NormalizedMessage


class GoogleBusinessAdapter(BaseChannelAdapter):

    @property
    def channel_type(self) -> str:
        return "google-business"

    async def normalize(self, payload: dict[str, Any]) -> NormalizedMessage:
        review = payload.get("review", payload)
        reviewer = review.get("reviewer", {})
        reviewer_name = reviewer.get("displayName", "") if isinstance(reviewer, dict) else ""
        star_rating = review.get("starRating", "")
        comment = review.get("comment", "")
        create_time = review.get("createTime", "")
        update_time = review.get("updateTime", "")
        review_reply = review.get("reviewReply", {})
        reply_comment = review_reply.get("comment", "") if isinstance(review_reply, dict) else ""

        location = payload.get("location", {})
        location_name = location.get("name", payload.get("location_name", ""))

        text_parts = [f"Google Business Review: {star_rating}"]
        if location_name:
            text_parts.append(f"Location: {location_name}")
        if reviewer_name:
            text_parts.append(f"By: {reviewer_name}")
        if create_time:
            text_parts.append(f"Date: {create_time}")
        if comment:
            text_parts.append(f"\n{comment}")
        if reply_comment:
            text_parts.append(f"\nOwner reply: {reply_comment}")

        return NormalizedMessage(
            channel_type="google-business",
            channel_id=location_name,
            peer_id=reviewer_name,
            message_id=review.get("reviewId", review.get("name", "")),
            text="\n".join(text_parts),
            source_type="other",
            raw=payload,
            extra={
                "star_rating": star_rating,
                "location": location_name,
                "has_reply": bool(reply_comment),
            },
        )
