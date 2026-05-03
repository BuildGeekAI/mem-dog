"""G2 webhook channel adapter.

Reference: https://docs.g2.com/docs/webhooks
"""

from __future__ import annotations

from typing import Any

from .base import BaseChannelAdapter, NormalizedMessage


class G2Adapter(BaseChannelAdapter):

    @property
    def channel_type(self) -> str:
        return "g2"

    async def normalize(self, payload: dict[str, Any]) -> NormalizedMessage:
        event = payload.get("event", "")
        data = payload.get("data", payload)
        review = data.get("review", data)

        title = review.get("title", "")
        comment = review.get("comment", review.get("text", ""))
        star_rating = review.get("star_rating", review.get("overall_rating", ""))
        product = review.get("product", data.get("product", {}))
        product_name = product.get("name", "") if isinstance(product, dict) else str(product)
        reviewer = review.get("reviewer", review.get("user", {}))
        reviewer_name = reviewer.get("name", "") if isinstance(reviewer, dict) else ""
        pros = review.get("pros", review.get("what_do_you_like_best", ""))
        cons = review.get("cons", review.get("what_do_you_dislike", ""))

        text_parts = [f"G2 Review: {event or 'new'}"]
        if star_rating:
            text_parts.append(f"Rating: {star_rating}/5")
        if product_name:
            text_parts.append(f"Product: {product_name}")
        if reviewer_name:
            text_parts.append(f"By: {reviewer_name}")
        if title:
            text_parts.append(f"Title: {title}")
        if pros:
            text_parts.append(f"\nPros: {pros[:500]}")
        if cons:
            text_parts.append(f"Cons: {cons[:500]}")
        if comment:
            text_parts.append(f"\n{comment[:1000]}")

        return NormalizedMessage(
            channel_type="g2",
            channel_id=product_name,
            peer_id=reviewer_name,
            message_id=review.get("id", ""),
            text="\n".join(text_parts),
            source_type="other",
            raw=payload,
            extra={"event": event, "rating": star_rating, "product": product_name},
        )
