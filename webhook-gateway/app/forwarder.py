"""Forward built envelopes to the existing memdog webhook API gateway.

Sends a POST request with the ``x-api-key`` header.  Retries up to 3
times with exponential back-off on transient failures.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

import httpx

from . import config

_log = logging.getLogger("openclaw_gateway.forwarder")

_MAX_RETRIES = 3
_BASE_DELAY_S = 0.5
_TIMEOUT_S = 30.0


@dataclass
class ForwardResult:
    """Outcome of a forwarding attempt."""

    success: bool
    status_code: int | None = None
    message_id: str | None = None
    trace_id: str | None = None
    error: str | None = None


async def forward_envelope(
    envelope: dict[str, Any],
    *,
    pipeline: str | None = None,
) -> ForwardResult:
    """POST *envelope* to the webhook gateway with retries.

    When ``pipeline="gke"``, routes to the in-cluster GKE receiver instead
    of the default Cloud Functions webhook gateway.

    Returns a ``ForwardResult`` describing the outcome.
    """
    url = config.get_webhook_url(pipeline)
    if not url:
        return ForwardResult(success=False, error="Webhook URL not configured")

    headers = {
        "Content-Type": "application/json",
        "x-api-key": config.WEBHOOK_API_KEY,
    }

    payload = {
        "data": envelope.get("data", {}),
        "meta_data": envelope.get("meta_data", {}),
    }

    last_error: str = ""
    async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code in (200, 201, 202):
                    body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                    return ForwardResult(
                        success=True,
                        status_code=resp.status_code,
                        message_id=body.get("message_id"),
                        trace_id=body.get("trace_id"),
                    )
                last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
                if resp.status_code < 500:
                    return ForwardResult(
                        success=False,
                        status_code=resp.status_code,
                        error=last_error,
                    )
            except (httpx.ConnectError, httpx.TimeoutException, httpx.ReadError) as exc:
                last_error = f"{type(exc).__name__}: {exc}"

            if attempt < _MAX_RETRIES:
                delay = _BASE_DELAY_S * (2 ** (attempt - 1))
                _log.warning(
                    "Forward attempt %d/%d failed (%s), retrying in %.1fs",
                    attempt, _MAX_RETRIES, last_error, delay,
                )
                await asyncio.sleep(delay)

    _log.error("All %d forward attempts failed: %s", _MAX_RETRIES, last_error)
    return ForwardResult(success=False, error=last_error)
