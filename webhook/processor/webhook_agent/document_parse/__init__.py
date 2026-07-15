"""Document parsing for webhook enrichment (Phase 1).

``DOCUMENT_PARSER=pypdf|docling``

- ``pypdf``: light extract for PDF + Office (default)
- ``docling``: PDF-only via ``docling-slim[format-pdf]``; Office still uses light libs
"""

from .router import parse_document

__all__ = ["parse_document"]
