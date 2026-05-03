"""Capterra review channel adapter."""

from __future__ import annotations

from typing import Any

from .base import BaseChannelAdapter, NormalizedMessage


class CapterraAdapter(BaseChannelAdapter):

    @property
    def channel_type(self) -> str:
        return "capterra"

    async def normalize(self, payload: dict[str, Any]) -> NormalizedMessage:
        review = payload.get("review", payload)
        overall_rating = review.get("overall_rating", review.get("rating", ""))
        title = review.get("title", review.get("headline", ""))
        pros = review.get("pros", "")
        cons = review.get("cons", "")
        comments = review.get("comments", review.get("overall_comments", ""))
        reviewer = review.get("reviewer", review.get("user", {}))
        reviewer_name = reviewer.get("name", "") if isinstance(reviewer, dict) else str(reviewer)
        product = review.get("product", payload.get("product", {}))
        product_name = product.get("name", "") if isinstance(product, dict) else str(product)

        text_parts = [f"Capterra Review: {overall_rating}/5" if overall_rating else "Capterra Review"]
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
        if comments:
            text_parts.append(f"\n{comments[:1000]}")

        return NormalizedMessage(
            channel_type="capterra",
            channel_id=product_name,
            peer_id=reviewer_name,
            message_id=review.get("id", ""),
            text="\n".join(text_parts),
            source_type="other",
            raw=payload,
            extra={"rating": overall_rating, "product": product_name},
        )
