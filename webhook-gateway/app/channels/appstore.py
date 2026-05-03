"""App Store / Play Store review channel adapter.

Handles app review data from Apple App Store Connect and Google Play Console.
"""

from __future__ import annotations

from typing import Any

from .base import BaseChannelAdapter, NormalizedMessage


class AppStoreAdapter(BaseChannelAdapter):

    @property
    def channel_type(self) -> str:
        return "appstore"

    async def normalize(self, payload: dict[str, Any]) -> NormalizedMessage:
        review = payload.get("review", payload)
        store = payload.get("store", review.get("store", ""))  # "apple" or "google"
        rating = review.get("rating", review.get("starRating", ""))
        title = review.get("title", "")
        body = review.get("body", review.get("text", review.get("comment", "")))
        author = review.get("author", review.get("reviewer", review.get("userName", "")))
        author_name = author.get("name", str(author)) if isinstance(author, dict) else str(author)
        app_name = payload.get("app_name", review.get("app", {}).get("name", "")) if isinstance(review.get("app"), dict) else payload.get("app_name", "")
        version = review.get("appVersion", review.get("version", ""))
        device = review.get("device", review.get("deviceMetadata", ""))
        created = review.get("created", review.get("createTime", ""))

        store_label = "App Store" if store == "apple" else "Play Store" if store == "google" else "App Review"

        text_parts = [f"{store_label}: {'★' * int(rating)}{'☆' * (5 - int(rating))}" if rating else store_label]
        if app_name:
            text_parts.append(f"App: {app_name}")
        if version:
            text_parts.append(f"Version: {version}")
        if author_name:
            text_parts.append(f"By: {author_name}")
        if title:
            text_parts.append(f"Title: {title}")
        if body:
            text_parts.append(f"\n{body}")

        return NormalizedMessage(
            channel_type="appstore",
            channel_id=app_name,
            peer_id=author_name,
            message_id=review.get("id", review.get("reviewId", "")),
            text="\n".join(text_parts),
            source_type="other",
            raw=payload,
            extra={"store": store, "rating": rating, "app": app_name, "version": version},
        )
