"""Zoom WebSocket event listener.

Connects to ``wss://ws.zoom.us/ws`` using Server-to-Server OAuth credentials
and dispatches events through the same pipeline as the webhook endpoint
(``ZoomAdapter.normalize()`` → ``build_envelope()`` → ``forward_envelope()``).

Runs as an opt-in background task (``ZOOM_WS_ENABLED=true``).
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
from typing import Any

import httpx
import websockets

from . import config
from .channels.zoom import ZoomAdapter
from .envelope import build_envelope
from .forwarder import forward_envelope
from .identity import resolve_user_id
from .memory import publish_to_memory

_log = logging.getLogger("openclaw_gateway.zoom_ws")

_ZOOM_OAUTH_URL = "https://zoom.us/oauth/token"
_ZOOM_WS_URL = "wss://ws.zoom.us/ws"
_HEARTBEAT_INTERVAL = 30  # seconds
_INITIAL_BACKOFF = 5  # seconds
_MAX_BACKOFF = 60  # seconds


class ZoomWebSocketClient:
    """Manages the Zoom WebSocket connection lifecycle."""

    def __init__(self) -> None:
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self._access_token: str = ""
        self._token_expires_at: float = 0.0
        self._adapter = ZoomAdapter()

    async def start(self) -> None:
        """Start the WebSocket listener as a background task."""
        if not config.ZOOM_CLIENT_ID or not config.ZOOM_CLIENT_SECRET or not config.ZOOM_ACCOUNT_ID:
            _log.error("Zoom WS enabled but ZOOM_CLIENT_ID, ZOOM_CLIENT_SECRET, or ZOOM_ACCOUNT_ID missing")
            return
        if not config.ZOOM_SUBSCRIPTION_ID:
            _log.error("Zoom WS enabled but ZOOM_SUBSCRIPTION_ID missing")
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run_forever())
        _log.info("Zoom WebSocket listener started")

    async def stop(self) -> None:
        """Signal the listener to stop and wait for clean shutdown."""
        if self._task is None:
            return
        self._stop_event.set()
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None
        _log.info("Zoom WebSocket listener stopped")

    # ------------------------------------------------------------------
    # OAuth
    # ------------------------------------------------------------------

    async def _get_access_token(self) -> str:
        """Return a valid OAuth access token, refreshing if needed."""
        if self._access_token and time.time() < self._token_expires_at - 300:
            return self._access_token

        credentials = base64.b64encode(
            f"{config.ZOOM_CLIENT_ID}:{config.ZOOM_CLIENT_SECRET}".encode()
        ).decode()

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                _ZOOM_OAUTH_URL,
                headers={"Authorization": f"Basic {credentials}"},
                data={
                    "grant_type": "account_credentials",
                    "account_id": config.ZOOM_ACCOUNT_ID,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        self._access_token = data["access_token"]
        self._token_expires_at = time.time() + data.get("expires_in", 3600)
        _log.info("Zoom OAuth token refreshed (expires_in=%s)", data.get("expires_in"))
        return self._access_token

    # ------------------------------------------------------------------
    # Connection loop
    # ------------------------------------------------------------------

    async def _run_forever(self) -> None:
        """Reconnect loop with exponential backoff."""
        backoff = _INITIAL_BACKOFF
        while not self._stop_event.is_set():
            try:
                token = await self._get_access_token()
                await self._listen(token)
                # If _listen returns normally, reset backoff
                backoff = _INITIAL_BACKOFF
            except asyncio.CancelledError:
                raise
            except Exception:
                _log.exception("Zoom WS error, reconnecting in %ds", backoff)
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=backoff)
                    return  # stop event was set
                except asyncio.TimeoutError:
                    pass
                backoff = min(backoff * 2, _MAX_BACKOFF)

    async def _listen(self, token: str) -> None:
        """Open WebSocket, send heartbeats, and dispatch events."""
        url = f"{_ZOOM_WS_URL}?subscriptionId={config.ZOOM_SUBSCRIPTION_ID}&access_token={token}"
        async with websockets.connect(url) as ws:
            _log.info("Zoom WebSocket connected")
            heartbeat_task = asyncio.create_task(self._heartbeat(ws))
            try:
                async for raw_message in ws:
                    if self._stop_event.is_set():
                        break
                    try:
                        payload = json.loads(raw_message)
                    except json.JSONDecodeError:
                        _log.warning("Zoom WS: non-JSON message ignored")
                        continue
                    # Skip heartbeat acknowledgements
                    if payload.get("module") == "heartbeat":
                        continue
                    asyncio.create_task(self._dispatch(payload))
            finally:
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass

    async def _heartbeat(self, ws: websockets.ClientConnection) -> None:
        """Send periodic heartbeat messages to keep the connection alive."""
        try:
            while True:
                await asyncio.sleep(_HEARTBEAT_INTERVAL)
                await ws.send(json.dumps({"module": "heartbeat"}))
        except asyncio.CancelledError:
            pass

    # ------------------------------------------------------------------
    # Event dispatch
    # ------------------------------------------------------------------

    async def _dispatch(self, payload: dict[str, Any]) -> None:
        """Process a Zoom event through the standard pipeline."""
        event = payload.get("event", "")
        _log.info("Zoom WS event: %s", event)

        try:
            msg = await self._adapter.normalize(payload)

            # Skip CRC events (shouldn't arrive over WS, but be safe)
            if msg.extra.get("zoom_crc"):
                return

            peer_id = msg.peer_id or msg.user_id or ""
            resolved_uid = await resolve_user_id("zoom", peer_id)

            envelope = build_envelope(msg, resolved_user_id=resolved_uid)
            result = await forward_envelope(envelope)

            if not result.success:
                _log.error("Zoom WS forward failed: %s", result.error)
                return

            if config.PUBLISH_TO_MEMORY:
                trace_id = envelope["_envelope_meta"]["trace_id"]
                await publish_to_memory(
                    msg,
                    resolved_user_id=resolved_uid,
                    trace_id=trace_id,
                )

            _log.info("Zoom WS event %s forwarded (msg_id=%s)", event, result.message_id)
        except Exception:
            _log.exception("Zoom WS dispatch error for event %s", event)


zoom_ws_client = ZoomWebSocketClient()
