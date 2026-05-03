"""TripAdvisor review channel adapter."""

from __future__ import annotations

from typing import Any

from .base import BaseChannelAdapter, NormalizedMessage


class TripAdvisorAdapter(BaseChannelAdapter):

    @property
    def channel_type(self) -> str:
        return "tripadvisor"

    async def normalize(self, payload: dict[str, Any]) -> NormalizedMessage:
        review = payload.get("review", payload)
        rating = review.get("rating", "")
        title = review.get("title", "")
        text = review.get("text", "")
        author = review.get("author", review.get("user", {}))
        author_name = author.get("username", author.get("name", "")) if isinstance(author, dict) else str(author)
        published_date = review.get("published_date", review.get("created_at", ""))
        location = payload.get("location", review.get("location", {}))
        location_name = location.get("name", "") if isinstance(location, dict) else str(location)

        text_parts = [f"TripAdvisor Review: {rating}/5" if rating else "TripAdvisor Review"]
        if location_name:
            text_parts.append(f"Location: {location_name}")
        if author_name:
            text_parts.append(f"By: {author_name}")
        if title:
            text_parts.append(f"Title: {title}")
        if text:
            text_parts.append(f"\n{text}")

        return NormalizedMessage(
            channel_type="tripadvisor",
            channel_id=location_name,
            peer_id=author_name,
            message_id=review.get("id", ""),
            text="\n".join(text_parts),
            source_type="other",
            raw=payload,
            extra={"rating": rating, "location": location_name},
        )
