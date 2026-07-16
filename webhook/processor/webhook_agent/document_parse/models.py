"""Parsed document schema (Phase 1 contract)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass
class ParsedDocument:
    parser: str
    parser_version: str
    mime_type: str
    page_count: int
    ocr_used: bool
    confidence: float
    markdown: str
    elements: list[dict[str, Any]] = field(default_factory=list)
    chunks: list[dict[str, Any]] = field(default_factory=list)
    parse_latency_ms: int = 0
    error: Optional[str] = None

    @property
    def text(self) -> str:
        return self.markdown

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
