"""Environment configuration for document parsing."""

from __future__ import annotations

import os

# pypdf (default) | docling (opt-in, PDF-only). Lean compose keeps pypdf.
DOCUMENT_PARSER: str = os.getenv("DOCUMENT_PARSER", "pypdf").strip().lower() or "pypdf"

# 0 = no page cap (docling default). For pypdf, 0 falls back to legacy 20-page cap.
_raw_max = os.getenv("DOCUMENT_PARSE_MAX_PAGES", "").strip()
DOCUMENT_PARSE_MAX_PAGES: int = int(_raw_max) if _raw_max.isdigit() else 0

# Phase 3 stubs — env accepted; routing not implemented yet.
DOCUMENT_OCR_ENABLED: bool = os.getenv("DOCUMENT_OCR_ENABLED", "false").strip().lower() in (
    "1",
    "true",
    "yes",
)

# Phase 3 stubs — none | llamaparse | gcp_layout
DOCUMENT_HARD_PARSER: str = (
    os.getenv("DOCUMENT_HARD_PARSER", "none").strip().lower() or "none"
)

PYPDF_LEGACY_MAX_PAGES = 20
