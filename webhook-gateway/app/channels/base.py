"""Abstract base class for channel adapters.

Every channel adapter normalizes a provider-specific payload into a
``NormalizedMessage`` that the envelope builder can wrap in a
``UniversalEnvelope``.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any


@dataclass
class NormalizedMessage:
    """Provider-agnostic representation of an inbound channel message."""

    channel_type: str
    channel_id: str | None = None
    peer_id: str | None = None
    thread_id: str | None = None
    message_id: str | None = None
    user_id: str | None = None
    text: str | None = None
    subject: str | None = None
    html: str | None = None
    attachments: list[dict[str, Any]] = field(default_factory=list)
    participants: list[str] = field(default_factory=list)
    recording_url: str | None = None
    source_type: str = "other"
    raw: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)
    # memdog data_id when content is already stored (pipeline processes only once, no loop)
    data_id: str | None = None
    is_downloaded: bool = False
    mime_type: str | None = None


class BaseChannelAdapter(abc.ABC):
    """Base class that every channel adapter must implement."""

    @property
    @abc.abstractmethod
    def channel_type(self) -> str:
        """Canonical channel type string (e.g. ``"email"``, ``"video"``)."""

    @abc.abstractmethod
    async def normalize(self, payload: dict[str, Any]) -> NormalizedMessage:
        """Convert a raw provider payload into a ``NormalizedMessage``."""

    def validate(self, payload: dict[str, Any], *, headers: dict[str, str] | None = None) -> None:
        """Optional hook for provider-specific validation (e.g. HMAC).

        Raise ``ValueError`` if validation fails.
        """
