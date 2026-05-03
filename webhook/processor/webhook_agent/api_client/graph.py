"""Graph API client — entity/relationship persistence.

After the LLM extracts typed entities and relationships from content,
this client persists them into the mem-dog graph layer via
``POST /api/v1/graph/entities/batch``.

Failures are logged and swallowed — graph persistence never blocks
viewpoint or embedding writes.
"""

import logging
from typing import Any

from .config import DEFAULT_TIMEOUT, MEM_DOG_API_URL
from .session import _session

logger = logging.getLogger("mem_dog.webhook.api_client.graph")


class GraphClient:
    """Thin wrapper around the /api/v1/graph endpoints."""

    def __init__(self, base_url: str = MEM_DOG_API_URL) -> None:
        self._batch_url = f"{base_url}/api/v1/graph/entities/batch"

    def batch_create_entities(
        self,
        data_id: str,
        entities: list[dict[str, Any]],
        relationships: list[dict[str, Any]],
        user_id: str,
    ) -> dict | None:
        """Batch create entities and relationships for a data item.

        Args:
            data_id: The data item ID.
            entities: List of ``{"entity_name": str, "entity_type": str, "confidence": float}``.
            relationships: List of ``{"source": str, "target": str, "rel_type": str}``.
            user_id: Owner user ID.

        Returns:
            API response dict or ``None`` on failure.
        """
        payload = {
            "data_id": data_id,
            "user_id": user_id,
            "entities": entities,
            "relationships": relationships,
        }
        try:
            resp = _session.post(
                self._batch_url, json=payload, timeout=DEFAULT_TIMEOUT,
            )
            if resp.status_code < 300:
                result = resp.json()
                logger.info(
                    "graph batch OK | data_id=%s  entities=%d  rels=%d",
                    data_id,
                    result.get("entities_created", 0),
                    result.get("relationships_created", 0),
                )
                return result
            logger.warning(
                "graph batch HTTP %d | data_id=%s  body=%s",
                resp.status_code, data_id, resp.text[:200],
            )
        except Exception as exc:
            logger.warning("graph batch failed | data_id=%s  error=%s", data_id, exc)
        return None


# Module-level singleton (mirrors ai_client pattern)
graph_client = GraphClient()
