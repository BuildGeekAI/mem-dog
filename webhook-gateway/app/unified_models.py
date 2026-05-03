"""Unified data models for cross-provider normalization.

Provides Pydantic models for common resource types that different
providers map their data into.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class UnifiedContact(BaseModel):
    """Normalized contact record across CRM providers."""

    id: str = ""
    first_name: str = ""
    last_name: str = ""
    email: str = ""
    phone: str = ""
    company: str = ""
    title: str = ""
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    raw: dict[str, Any] = Field(default_factory=dict)


class UnifiedCalendarEvent(BaseModel):
    """Normalized calendar event across calendar providers."""

    id: str = ""
    title: str = ""
    description: str = ""
    start: Optional[str] = None
    end: Optional[str] = None
    attendees: list[str] = Field(default_factory=list)
    location: str = ""
    organizer: str = ""
    created_at: Optional[str] = None
    raw: dict[str, Any] = Field(default_factory=dict)
