"""Webhook ADK Agent.

Thin ADK agent definition.  All business logic lives in dedicated modules:

* :mod:`router`        — four-layer data-type detection + sub-agent dispatch
* :mod:`classifier`    — LLM classification via the model server
* :mod:`group_context` — user/group identity and shared memory management
* :mod:`api_client`    — all HTTP calls (data, memory, stats)
* :mod:`sub_agents`    — 26 typed sub-agents

Deployed to Cloud Run as a persistent ``adk api_server`` service.
The processor Cloud Function calls it via a plain HTTP POST to ``/run``.

Orchestrator model
------------------
The root agent uses the **data processing pipeline AI config** for orchestration:
primary model (default Gemini 3.0 Flash).  If ``ADK_MODEL`` is set it overrides;
otherwise ``DATA_PIPELINE_AI_PRIMARY_MODEL`` is used so one config drives both
orchestrator and sub-agents.  For open models, set ``ADK_MODEL=openai/gemma`` and
``MODEL_SERVER_URL`` to the model server base URL.

Classifier and sub-agents use :mod:`model_client`, which uses the same data
pipeline config (primary → Ollama Cloud fallback → model server).

Configure via environment variables::

    DATA_PIPELINE_AI_PRIMARY_MODEL — Primary model for orchestration and data
        processing (default: ``gemini/gemini-3-flash``).  Used as ADK orchestrator
        model when ADK_MODEL is not set.
    ADK_MODEL — Override for the ADK orchestrator only.  If unset, equals
        DATA_PIPELINE_AI_PRIMARY_MODEL.
    MODEL_SERVER_URL — Required when ADK_MODEL is ``openai/<anything>``.
        Base URL of the model server (Cloud Run B).
"""

import json
import logging
import os
import uuid
from pathlib import Path
from typing import Optional

# Load shared AI model defaults from config/ai.env (repo root, local dev only).
try:
    from dotenv import load_dotenv
    _ai_env = Path(__file__).resolve().parents[3] / "config" / "ai.env"
    if _ai_env.exists():
        load_dotenv(_ai_env)
except (ImportError, IndexError):
    pass

from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

from .api_client import stats_client
from .router import route_payload

# ---------------------------------------------------------------------------
# Orchestrator model — Gemini by default, optional open model server
# ---------------------------------------------------------------------------

_MODEL_SERVER_URL: str = os.environ.get("MODEL_SERVER_URL", "").rstrip("/")
# Orchestrator uses data pipeline primary model unless ADK_MODEL is set.
_ADK_MODEL: str = (
    os.environ.get("ADK_MODEL")
    or os.environ.get("DATA_PIPELINE_AI_PRIMARY_MODEL",
                      os.environ.get("GEMINI_LITELLM_MODEL", "gemini/gemini-3.1-pro-preview"))
)


def _is_gemini_model(model: str) -> bool:
    """True if the LiteLLM model string uses Gemini (vertex_ai or gemini provider)."""
    return model.startswith("vertex_ai/") or model.startswith("gemini/")


def _build_model() -> LiteLlm:
    """Construct the LiteLlm connector for the ADK orchestrator.

    Uses Gemini 3 by default (ADK_MODEL e.g. vertex_ai/gemini-3-flash).  When
    ADK_MODEL is ``openai/<anything>``, requires MODEL_SERVER_URL and routes
    to the Ollama model server for open-model orchestration.

    Returns:
        A :class:`~google.adk.models.lite_llm.LiteLlm` instance.

    Raises:
        RuntimeError: If ADK_MODEL is openai/ but MODEL_SERVER_URL is not set.
    """
    if _is_gemini_model(_ADK_MODEL):
        return LiteLlm(model=_ADK_MODEL)
    if not _MODEL_SERVER_URL:
        raise RuntimeError(
            "MODEL_SERVER_URL is not set.  When using open models (ADK_MODEL=openai/...), "
            "set MODEL_SERVER_URL to the model server base URL, or switch to Gemini by "
            "setting ADK_MODEL=vertex_ai/gemini-3-flash (default)."
        )
    return LiteLlm(
        model=_ADK_MODEL,
        api_base=f"{_MODEL_SERVER_URL}/v1",
        api_key="none",
    )

logger = logging.getLogger("mem_dog.webhook.agent")

# Unique identity for this *main* agent instance (sub-agents have their own)
AGENT_INSTANCE_ID = f"webhook-agent-{uuid.uuid4().hex[:12]}"

logger.info("Webhook agent initialised", extra={"agent_instance_id": AGENT_INSTANCE_ID})


def log_webhook_data(payload_json: str) -> dict:
    """Log the webhook payload to Cloud Logging with structured metadata.

    Args:
        payload_json: The webhook payload as a JSON string.

    Returns:
        Status dict with ``agent_instance_id`` and ``payload_keys``.
    """
    try:
        payload = json.loads(payload_json)
    except (json.JSONDecodeError, ValueError):
        payload = {"raw": payload_json}

    logger.info(
        "Webhook payload received by ADK agent",
        extra={
            "webhook_payload": payload,
            "source": "webhook_agent",
            "agent_instance_id": AGENT_INSTANCE_ID,
        },
    )
    return {
        "status": "success",
        "agent_instance_id": AGENT_INSTANCE_ID,
        "message": "Payload logged to Cloud Logging.",
        "payload_keys": list(payload.keys()) if isinstance(payload, dict) else [],
    }


def route_data(payload_json: str) -> dict:
    """Detect the payload data type and dispatch to the correct sub-agent.

    Runs the four-layer detection pipeline (explicit field → LLM
    classifier → MIME registry → URL extension → fallback), resolves
    the caller's group context, and writes a memory-of-record.

    Args:
        payload_json: The incoming webhook payload as a JSON string.

    Returns:
        Routing result dict with ``data_type``, group context fields,
        agent manifest, and the write record result.
    """
    return route_payload(payload_json)


def get_routing_stats() -> dict:
    """Return the current live per-agent-type data counts.

    Returns:
        ``AgentTypeStats`` dict with ``counts``, ``total``, and
        ``last_updated``.
    """
    return stats_client.get_counts()


root_agent = Agent(
    name="webhook_processor_agent",
    model=_build_model(),
    description=(
        "Agent that processes incoming webhook payloads by detecting their data type "
        "and routing them to the correct typed sub-agent. "
        f"This instance is identified as {AGENT_INSTANCE_ID}."
    ),
    instruction=(
        "You are a webhook processing agent for the memdog private AI system. "
        f"Your unique instance ID is {AGENT_INSTANCE_ID}. "
        "When you receive a webhook payload:\n"
        "1. Log the payload using the log_webhook_data tool.\n"
        "2. Route and store it using the route_data tool — this detects the data type "
        "   (video, audio, PDF, JSON, LiDAR, etc.) and dispatches to the right sub-agent.\n"
        "3. Optionally call get_routing_stats to report the current data-type counts.\n"
        "Always process steps 1 and 2 for every payload you receive."
    ),
    tools=[log_webhook_data, route_data, get_routing_stats],
)
