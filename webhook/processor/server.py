"""Direct webhook processing server.

Thin FastAPI server that exposes ``POST /process-webhook`` — a direct call
to :func:`~webhook_agent.router.route_payload` with **no LLM orchestration**.

This bypasses the ADK ``/run_sse`` path (where Gemma is asked to choose which
tool to call) because small models like Gemma 3 4B are not reliable enough at
tool-calling to act as orchestrators.  The routing logic itself is deterministic
Python code and does not need an LLM to decide to invoke it.

Endpoints
---------
POST /process-webhook
    Body: ``{"payload_json": "<escaped-json-string>"}``
    Calls ``route_payload(payload_json)`` and returns the routing result.

GET /health
    Returns ``{"status": "ok"}`` — used by Cloud Run health checks.
"""

import logging
import os
import sys

# Configure root logger so mem_dog.* INFO messages are visible.
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

# Ensure the parent directory is on sys.path so ``webhook_agent`` is importable
# when this file is run as a script (i.e. ``python server.py``).
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from webhook_agent.router import route_payload

logger = logging.getLogger("mem_dog.webhook.server")

app = FastAPI(
    title="memdog Webhook Agent Server",
    description="Direct webhook routing server — no LLM orchestration.",
    version="1.0.0",
)


class ProcessWebhookRequest(BaseModel):
    """Request body for POST /process-webhook."""
    payload_json: str


class HealthResponse(BaseModel):
    status: str


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Cloud Run health check."""
    return HealthResponse(status="ok")


@app.post("/process-webhook")
async def process_webhook(request: ProcessWebhookRequest) -> dict:
    """Route a webhook payload directly to the correct sub-agent.

    Calls :func:`~webhook_agent.router.route_payload` synchronously and
    returns its result.  All telemetry spans are written inside
    ``route_payload`` — no extra work needed here.

    Args:
        request: JSON body with ``payload_json`` field containing the
            serialised webhook payload (including any ``__trace_context__``
            injected by the processor).

    Returns:
        The routing result dict from ``route_payload``.

    Raises:
        HTTPException 500: If ``route_payload`` raises an unhandled exception.
    """
    try:
        result = route_payload(request.payload_json)
        logger.info(
            "Webhook routed successfully",
            extra={
                "data_type": result.get("data_type"),
                "user_id": result.get("user_id"),
                "process_status": result.get("process", {}).get("status"),
            },
        )
        return result
    except Exception as exc:
        logger.exception("route_payload raised: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
