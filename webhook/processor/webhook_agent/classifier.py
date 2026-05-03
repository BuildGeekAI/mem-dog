"""Light LLM classifier for data-type detection.

Uses the Gemma model hosted on the model server to classify an incoming
payload into one of the 26 known agent types.

Inference is handled entirely by the dedicated model server (Cloud Run B),
which exposes an OpenAI-compatible ``/v1/chat/completions`` endpoint.  No
model runs in-process.  See :mod:`model_client` for transport details.

Graceful fallback
-----------------
Any inference failure causes :meth:`LightLLMClassifier.classify` to return
``None``.  The router then falls through to the MIME-registry layer so no
payload is ever dropped.
"""

import logging
from typing import Optional

from .sub_agents import AGENT_REGISTRY

logger = logging.getLogger("mem_dog.webhook.classifier")

VALID_AGENT_TYPES: list[str] = sorted(AGENT_REGISTRY.keys())

_PROMPT_TEMPLATE = """\
Classify the following data payload into exactly one of these types:
{types}

Payload summary (field names and value previews):
{summary}

Reply with ONLY the type name from the list above — no explanation, \
no punctuation, just the type name."""


class LightLLMClassifier:
    """Classifies payload data type using the model server.

    All inference is delegated to the remote model server via
    :func:`~model_client.chat_for_data_type`.  Designed to be instantiated
    once at module load (singleton pattern).
    """

    def _summarise_payload(self, payload: dict) -> str:
        """Build a compact field+value preview for the classification prompt.

        Limits to the first 10 fields and truncates string values at 80
        characters to keep the prompt short.
        """
        lines: list[str] = []
        for key, value in list(payload.items())[:10]:
            if isinstance(value, str):
                preview = value[:80]
            elif isinstance(value, (list, dict)):
                preview = f"[{type(value).__name__}, len={len(value)}]"
            else:
                preview = str(value)[:40]
            lines.append(f"  {key}: {preview}")
        return "\n".join(lines) or "  (empty payload)"

    def classify(self, payload: dict, exclude_types: list[str] | None = None) -> Optional[str]:
        """Classify *payload* and return an agent type string or ``None``.

        Sends a single-turn prompt to the model server and parses the
        response.  Any failure returns ``None`` so the router can fall
        through to the MIME-registry layer.

        Args:
            payload: The decoded webhook payload dict.
            exclude_types: Optional list of agent types to exclude from
                the candidate list (e.g. ``["url_download"]`` when data
                is already downloaded).

        Returns:
            An ``AGENT_TYPE`` string from ``VALID_AGENT_TYPES``, or
            ``None`` if classification fails or is inconclusive.
        """
        from . import model_client

        candidates = VALID_AGENT_TYPES
        if exclude_types:
            candidates = [t for t in candidates if t not in exclude_types]

        prompt = _PROMPT_TEMPLATE.format(
            types=", ".join(candidates),
            summary=self._summarise_payload(payload),
        )
        messages = [{"role": "user", "content": prompt}]

        try:
            raw = model_client.chat_for_data_type(
                messages, agent_type="binary_blob", max_tokens=15, temperature=1.0,
            ).lower()
        except Exception as exc:
            logger.warning("Classifier model server call failed (%s): %s", type(exc).__name__, exc)
            return None

        # Exact match
        if raw in candidates:
            logger.info("LLM classified payload as: %s", raw)
            return raw

        # Fuzzy substring match (handles responses like "this is pdf type")
        for known_type in candidates:
            if known_type in raw:
                logger.info("LLM classified payload as: %s (fuzzy from %r)", known_type, raw)
                return known_type

        logger.warning("LLM returned unrecognised type %r; falling back", raw)
        return None


# Module-level singleton
classifier: LightLLMClassifier = LightLLMClassifier()
