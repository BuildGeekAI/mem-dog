"""Docling PDF-only text extract via docling-parse (no torch / DocumentConverter).

Office formats stay on the pypdf/python-docx path — this backend rejects
non-PDF so the router can fall through.
"""

from __future__ import annotations

import logging
import time
from io import BytesIO
from typing import Any

from .config import DOCUMENT_PARSE_MAX_PAGES
from .models import ParsedDocument

logger = logging.getLogger("mem_dog.webhook.document_parse.docling")


def _is_pdf(mime_type: str) -> bool:
    return "pdf" in (mime_type or "").lower()


def parse(content_bytes: bytes, mime_type: str) -> ParsedDocument:
    if not _is_pdf(mime_type):
        raise ValueError(
            f"docling backend is PDF-only; got mime={mime_type!r} "
            "(Office formats use pypdf/python-docx)"
        )

    try:
        from docling_parse.pdf_parser import ContentConfig, ContentLevel, DoclingPdfParser
    except ImportError as exc:
        raise RuntimeError(
            "docling-parse is not installed; "
            "set DOCUMENT_PARSER=pypdf or pip install 'docling-slim[format-pdf]'"
        ) from exc

    try:
        import docling_parse

        version = getattr(docling_parse, "__version__", "unknown")
    except Exception:
        version = "unknown"
    try:
        import importlib.metadata as _md

        version = _md.version("docling-parse")
    except Exception:
        pass

    t0 = time.perf_counter()
    content_config = ContentConfig(
        char_cells_content_level=ContentLevel.SKIP,
        word_cells_content_level=ContentLevel.COMPUTE_AND_MATERIALIZE,
        line_cells_content_level=ContentLevel.COMPUTE_AND_MATERIALIZE,
        shapes_content_level=ContentLevel.SKIP,
        bitmaps_content_level=ContentLevel.SKIP,
    )

    parser = DoclingPdfParser()
    pdf_doc = parser.load(
        BytesIO(content_bytes),
        lazy=False,
        content_config=content_config,
    )
    try:
        total_pages = int(pdf_doc.number_of_pages())
        max_pages = DOCUMENT_PARSE_MAX_PAGES if DOCUMENT_PARSE_MAX_PAGES > 0 else total_pages
        pages_to_read = min(total_pages, max_pages) if max_pages else total_pages

        text_parts: list[str] = []
        elements: list[dict[str, Any]] = []
        pages_with_text = 0

        for page_no in range(1, pages_to_read + 1):
            page = pdf_doc.get_page(page_no, content_config=content_config)
            lines = [
                cell.text
                for cell in (page.textline_cells or [])
                if getattr(cell, "text", None) and cell.text.strip()
            ]
            if not lines:
                continue
            pages_with_text += 1
            page_text = "\n".join(lines)
            text_parts.append(f"[Page {page_no}]\n{page_text}")
            elements.append(
                {
                    "type": "page",
                    "text": page_text,
                    "page": page_no,
                    "section_path": [f"Page {page_no}"],
                    "element_type": "narrative",
                }
            )

        markdown = "\n\n".join(text_parts)
        latency = int((time.perf_counter() - t0) * 1000)
        confidence = pages_with_text / pages_to_read if pages_to_read else 0.0

        return ParsedDocument(
            parser="docling",
            parser_version=version,
            mime_type=mime_type,
            page_count=total_pages,
            ocr_used=False,
            confidence=round(confidence, 3),
            markdown=markdown,
            elements=elements,
            chunks=[
                {
                    "text": el["text"],
                    "page": el["page"],
                    "section_path": el["section_path"],
                    "element_type": el["element_type"],
                }
                for el in elements
            ],
            parse_latency_ms=latency,
        )
    finally:
        try:
            pdf_doc.unload()
        except Exception:
            pass
