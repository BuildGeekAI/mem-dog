"""Persist parsed artifacts to the mem-dog API."""

from __future__ import annotations

import logging
from typing import Any, Optional

from ..api_client import data_client
from .models import ParsedDocument

logger = logging.getLogger("mem_dog.webhook.document_parse.persist")


def persist_parsed_document(
    data_id: str,
    parsed: ParsedDocument,
    user_id: Optional[str] = None,
) -> dict[str, Any]:
    """Best-effort write of parsed.md + document.json via API."""
    try:
        return data_client.store_parsed(
            data_id=data_id,
            markdown=parsed.markdown,
            document=parsed.to_dict(),
            user_id=user_id,
        )
    except Exception as exc:
        logger.warning(
            "Failed to persist parsed artifacts for %s: %s", data_id, exc, exc_info=True
        )
        return {"status": "error", "error": str(exc)}
