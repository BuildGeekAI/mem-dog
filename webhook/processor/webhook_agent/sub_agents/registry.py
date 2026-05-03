"""MIME registry for sub-agent lookup.

Agents register their ``MIME_PATTERNS`` at import time.  The router calls
``MimeRegistry.match()`` to find the best agent for a given MIME type
without any hardcoded ``if/elif`` chains.

Lookup priority
---------------
1. Exact match   — ``"application/pdf"`` → ``PdfAgent``
2. Prefix match  — ``"video/custom"``    → ``VideoStreamAgent`` (``"video/"`` prefix)
3. ``None``      — falls through to the next routing layer
"""

import logging
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .base import BaseSubAgent

logger = logging.getLogger("mem_dog.webhook.sub_agents.registry")


class MimeRegistry:
    """Best-match MIME-type → agent lookup table.

    Built once at import time from the ``MIME_PATTERNS`` declared on each
    registered agent class.
    """

    def __init__(self) -> None:
        # exact mime → agent instance
        self._exact: dict[str, "BaseSubAgent"] = {}
        # mime prefix (e.g. "video/") → agent instance
        self._prefix: dict[str, "BaseSubAgent"] = {}

    def register(self, agent: "BaseSubAgent") -> None:
        """Register all MIME patterns declared by *agent*.

        Args:
            agent: An instantiated sub-agent with ``MIME_PATTERNS`` populated.
        """
        for pattern in agent.MIME_PATTERNS:
            if pattern.endswith("/") or pattern.endswith("/*"):
                # Normalise to "video/" prefix form
                prefix = pattern.rstrip("*")
                self._prefix[prefix] = agent
            else:
                self._exact[pattern] = agent
        logger.debug(
            "Registered %s with patterns: %s",
            agent.AGENT_TYPE,
            agent.MIME_PATTERNS,
        )

    def match(self, mime_type: str) -> Optional["BaseSubAgent"]:
        """Return the best-matching agent for *mime_type*, or ``None``.

        Args:
            mime_type: A MIME type string (e.g. ``"application/pdf"``).

        Returns:
            The matching agent instance, or ``None`` if no pattern matches.
        """
        if not mime_type:
            return None

        # 1. Exact match
        agent = self._exact.get(mime_type)
        if agent:
            return agent

        # 2. Prefix match — check longest prefix first
        for prefix in sorted(self._prefix, key=len, reverse=True):
            if mime_type.startswith(prefix):
                return self._prefix[prefix]

        return None
