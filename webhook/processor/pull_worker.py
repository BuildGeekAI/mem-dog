"""GKE NATS subscriber for the webhook pipeline.

Long-running async process that:
1. Subscribes to the ``webhook.inbound`` NATS subject with a queue group
2. Extracts trace context from NATS message headers
3. Forwards the payload to the webhook agent service via HTTP
4. Uses queue group ``webhook-workers`` for load-balanced consumption
5. Writes a ``webhook.processor`` OTel span for each message processed
"""

import asyncio
import json
import logging
import os
import signal
import sys
import uuid
from datetime import datetime, timezone

import nats as nats_client
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("mem_dog.webhook.pull_worker")

NATS_URL = os.environ.get("NATS_URL", "nats://nats.webhook-pipeline.svc.cluster.local:4222")
NATS_SUBJECT = os.environ.get("NATS_SUBJECT", "webhook.inbound")
NATS_QUEUE_GROUP = os.environ.get("NATS_QUEUE_GROUP", "webhook-workers")
AGENT_URL = os.environ.get("AGENT_URL", "http://webhook-agent.webhook-pipeline.svc.cluster.local:8080")
MEM_DOG_API_URL = os.environ.get("MEM_DOG_API_URL", "").rstrip("/")
MEM_DOG_API_KEY = os.environ.get("MEM_DOG_API_KEY", "")
_TELEMETRY_TIMEOUT = 8


def _write_processor_span(
    *,
    trace_id: str,
    span_id: str,
    parent_span_id: str,
    trace_memory_id: str,
    start_time: datetime,
    end_time: datetime,
    status_code: str,
    user_id: str,
) -> None:
    """Write a processor/pull-worker OTel span to the tracing memory."""
    if not MEM_DOG_API_URL or not trace_memory_id:
        return
    duration_ms = (end_time - start_time).total_seconds() * 1000
    span = {
        "trace_id": trace_id,
        "span_id": span_id,
        "parent_span_id": parent_span_id,
        "name": "webhook.processor",
        "kind": "CONSUMER",
        "service_name": "webhook-pull-worker",
        "service_type": "gke_deployment",
        "status": {"code": status_code, "message": ""},
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "duration_ms": round(duration_ms, 3),
    }
    tags = [
        f"trace_id:{trace_id}",
        f"span_id:{span_id}",
        f"parent_span_id:{parent_span_id}",
        "stage:processor",
        "service:webhook-pull-worker",
        f"status:{status_code}",
        "kind:CONSUMER",
        "source:webhook_telemetry",
    ]
    try:
        req_headers = {}
        if MEM_DOG_API_KEY:
            req_headers["x-api-key"] = MEM_DOG_API_KEY
        requests.post(
            f"{MEM_DOG_API_URL}/api/v1/data",
            data={
                "content": json.dumps(span, default=str),
                "name": f"webhook.processor | {status_code}",
                "description": f"[webhook-pull-worker] webhook.processor — CONSUMER span — {status_code}",
                "tags": ",".join(tags),
                "memory_ids": trace_memory_id,
                "exclusive": "true",
                "owner_user_id": user_id,
            },
            headers=req_headers,
            timeout=_TELEMETRY_TIMEOUT,
        )
    except Exception as exc:
        logger.warning("Failed to write processor span: %s", exc)


def process_message(data: bytes, headers: dict) -> bool:
    """Forward a single NATS message to the webhook agent.

    Returns True on success, False on failure.
    """
    proc_start = datetime.now(timezone.utc)

    try:
        payload_str = data.decode("utf-8")
        payload = json.loads(payload_str)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.error("Failed to decode message: %s", exc)
        return True  # don't retry malformed messages

    trace_id = headers.get("X-Trace-Id", "")
    receiver_span_id = headers.get("X-Span-Id", "")
    trace_memory_id = headers.get("X-Trace-Memory-Id", "")
    user_id = headers.get("X-User-Id", "")
    processor_span_id = uuid.uuid4().hex[:16]

    if trace_id or receiver_span_id:
        tc = {"trace_id": trace_id, "span_id": processor_span_id, "parent_span_id": receiver_span_id}
        if trace_memory_id:
            tc["trace_memory_id"] = trace_memory_id
        if "meta_data" in payload and isinstance(payload["meta_data"], dict):
            payload["meta_data"]["__trace_context__"] = tc
            # Also inject trace_memory_id into nested tracing group if present
            if trace_memory_id and isinstance(payload["meta_data"].get("tracing"), dict):
                payload["meta_data"]["tracing"].setdefault("trace_memory_id", trace_memory_id)
        elif "telemetry" in payload and isinstance(payload["telemetry"], dict):
            payload["telemetry"]["__trace_context__"] = tc
        elif "data" in payload and isinstance(payload["data"], dict):
            payload["data"]["__trace_context__"] = tc

    # Write early "PROCESSING" span so tracing is visible immediately
    if trace_memory_id:
        _write_processor_span(
            trace_id=trace_id, span_id=processor_span_id,
            parent_span_id=receiver_span_id, trace_memory_id=trace_memory_id,
            start_time=proc_start, end_time=datetime.now(timezone.utc),
            status_code="PROCESSING", user_id=user_id,
        )

    agent_payload = {"payload_json": json.dumps(payload)}
    status = "OK"

    try:
        resp = requests.post(
            f"{AGENT_URL}/process-webhook",
            json=agent_payload,
            timeout=90,
        )
        if resp.status_code == 200:
            logger.info(
                "Message processed | trace=%s user=%s",
                trace_id[:8] if trace_id else "-",
                user_id[:8] if user_id else "-",
            )
            success = True
        else:
            logger.warning(
                "Agent returned %d: %s",
                resp.status_code, resp.text[:200],
            )
            status = "ERROR"
            success = False
    except requests.RequestException as exc:
        logger.error("Failed to reach agent: %s", exc)
        status = "ERROR"
        success = False

    _write_processor_span(
        trace_id=trace_id, span_id=processor_span_id,
        parent_span_id=receiver_span_id, trace_memory_id=trace_memory_id,
        start_time=proc_start, end_time=datetime.now(timezone.utc),
        status_code=status, user_id=user_id,
    )
    return success


async def run():
    """Connect to NATS and subscribe to the webhook subject."""
    nc = await nats_client.connect(NATS_URL)
    logger.info(
        "Connected to NATS | url=%s subject=%s queue=%s agent=%s",
        NATS_URL, NATS_SUBJECT, NATS_QUEUE_GROUP, AGENT_URL,
    )

    async def message_handler(msg):
        headers = {}
        if msg.headers:
            for k, v in msg.headers.items():
                headers[k] = v if isinstance(v, str) else v[0] if v else ""

        loop = asyncio.get_event_loop()
        success = await loop.run_in_executor(
            None, process_message, msg.data, headers
        )
        if not success:
            logger.warning("Message processing failed, will not be retried (NATS core)")

    await nc.subscribe(NATS_SUBJECT, queue=NATS_QUEUE_GROUP, cb=message_handler)
    logger.info("Subscribed to %s (queue=%s)", NATS_SUBJECT, NATS_QUEUE_GROUP)

    stop = asyncio.Event()

    def signal_handler():
        logger.info("Shutdown signal received")
        stop.set()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)

    await stop.wait()
    logger.info("Draining NATS connection...")
    await nc.drain()
    logger.info("Shutdown complete")


if __name__ == "__main__":
    asyncio.run(run())
