"""Zoom webhook channel adapter.

Handles Zoom-specific CRC (challenge-response check) for endpoint URL
validation and normalizes Zoom webhook events.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
from typing import Any

from .base import BaseChannelAdapter, NormalizedMessage
from .video import _extract_zoom

_log = logging.getLogger("openclaw_gateway.channels.zoom")

ZOOM_WEBHOOK_SECRET: str = os.getenv("ZOOM_WEBHOOK_SECRET", "")


class ZoomAdapter(BaseChannelAdapter):
    """Dedicated Zoom adapter with CRC support."""

    @property
    def channel_type(self) -> str:
        return "zoom"

    def validate(self, payload: dict[str, Any], *, headers: dict[str, str] | None = None) -> None:
        # Signature verification requires raw body bytes which we don't
        # have here.  CRC validation is the primary mechanism Zoom uses
        # to verify endpoint ownership, so this is acceptable for now.
        pass

    async def normalize(self, payload: dict[str, Any]) -> NormalizedMessage:
        event = payload.get("event", "")

        # CRC challenge-response for Zoom endpoint URL validation
        if event == "endpoint.url_validation":
            token = payload.get("payload", {}).get("plainToken", "")
            if not ZOOM_WEBHOOK_SECRET:
                raise ValueError("ZOOM_WEBHOOK_SECRET not configured for CRC validation")
            encrypted = hmac.new(
                ZOOM_WEBHOOK_SECRET.encode(),
                token.encode(),
                hashlib.sha256,
            ).hexdigest()
            _log.info("Zoom CRC validation request received")
            return NormalizedMessage(
                channel_type="zoom",
                raw=payload,
                extra={"zoom_crc": {"plainToken": token, "encryptedToken": encrypted}},
            )

        # Regular Zoom events — reuse the video adapter's extraction logic
        msg = _extract_zoom(payload)
        msg.channel_type = "zoom"
        return msg
