"""Stats API client.

Manages live per-agent-type data counts via the mem-dog
``/api/v1/stats/agent-types`` endpoints.
"""

import logging
from typing import Any

import requests

from .config import DEFAULT_TIMEOUT, MEM_DOG_API_URL
from .session import _session

logger = logging.getLogger("mem_dog.webhook.api_client.stats")


class StatsClient:
    """Thin wrapper around the /api/v1/stats endpoints."""

    def __init__(self, base_url: str = MEM_DOG_API_URL) -> None:
        self._base = f"{base_url}/api/v1/stats/agent-types"
        self._stats_base = f"{base_url}/api/v1/stats"

    def increment(self, agent_type: str) -> dict[str, Any]:
        """Increment the count for ``agent_type`` by 1.

        Failures are logged and swallowed so that a stats outage never
        prevents data from being stored.

        Args:
            agent_type: The agent type string (e.g. ``"pdf"``).

        Returns:
            The updated counts dict, or an error dict on failure.
        """
        try:
            resp = _session.post(
                f"{self._base}/{agent_type}/increment", timeout=DEFAULT_TIMEOUT
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.warning("Failed to increment stats for %s: %s", agent_type, exc)
            return {"status": "error", "agent_type": agent_type, "error": str(exc)}

    def decrement(self, agent_type: str) -> dict[str, Any]:
        """Decrement the count for ``agent_type`` by 1 (floor 0).

        Args:
            agent_type: The agent type string.

        Returns:
            The updated counts dict, or an error dict on failure.
        """
        try:
            resp = _session.post(
                f"{self._base}/{agent_type}/decrement", timeout=DEFAULT_TIMEOUT
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.warning("Failed to decrement stats for %s: %s", agent_type, exc)
            return {"status": "error", "agent_type": agent_type, "error": str(exc)}

    def record_token_usage(
        self,
        user_id: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        model: str = "",
        agent_type: str = "",
        duration_ms: float | None = None,
    ) -> dict[str, Any]:
        """Report a token usage event to the API (best-effort).

        Failures are logged and swallowed so that a stats outage never
        blocks the data processing pipeline.
        """
        body = {
            "user_id": user_id,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "model": model,
            "agent_type": agent_type,
        }
        if duration_ms is not None:
            body["duration_ms"] = duration_ms
        try:
            resp = _session.post(
                f"{self._stats_base}/token-usage",
                json=body,
                timeout=DEFAULT_TIMEOUT,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.warning("Failed to record token usage: %s", exc)
            return {"status": "error", "error": str(exc)}

    def get_counts(self) -> dict[str, Any]:
        """Return the current per-type counts.

        Returns:
            ``AgentTypeStats`` dict with ``counts``, ``total``, and
            ``last_updated`` fields, or an error dict on failure.
        """
        try:
            resp = _session.get(self._base, timeout=DEFAULT_TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.warning("Failed to fetch agent-type stats: %s", exc)
            return {"counts": {}, "total": 0, "last_updated": "", "error": str(exc)}
