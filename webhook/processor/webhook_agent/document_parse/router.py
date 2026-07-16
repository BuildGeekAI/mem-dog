"""Parse router — DOCUMENT_PARSER flag with pypdf fallback.

Docling is PDF-only (``docling-slim[format-pdf]``). Office always uses
the light pypdf/python-docx backends.
"""

from __future__ import annotations

import logging

from . import config
from .models import ParsedDocument

logger = logging.getLogger("mem_dog.webhook.document_parse")


def _is_pdf(mime_type: str) -> bool:
    return "pdf" in (mime_type or "").lower()


def parse_document(content_bytes: bytes, mime_type: str) -> ParsedDocument:
    """Parse document bytes using the configured backend.

    When ``DOCUMENT_PARSER=docling`` and mime is PDF, tries Docling then
    falls back to pypdf. Non-PDF always uses the light Office extractors.
    """
    parser = config.DOCUMENT_PARSER
    if parser not in ("pypdf", "docling"):
        logger.warning("Unknown DOCUMENT_PARSER=%s — using pypdf", parser)
        parser = "pypdf"

    if parser == "docling" and _is_pdf(mime_type):
        try:
            from . import docling_backend

            return docling_backend.parse(content_bytes, mime_type)
        except Exception as exc:
            logger.warning(
                "Docling PDF parse failed (%s); falling back to pypdf",
                exc,
                exc_info=True,
            )

    from . import pypdf_backend

    return pypdf_backend.parse(content_bytes, mime_type)
