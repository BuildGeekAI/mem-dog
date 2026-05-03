"""Shared HTTP session for all mem-dog API clients.

All five API client modules import :data:`_session` from here instead of
calling ``requests`` directly, so retry and backoff logic lives in exactly
one place.

Retry policy
------------
* **3 connect retries** — covers ``ssl.SSLEOFError`` and other transient
  SSL / TCP handshake failures that are the most common failure mode when
  talking to the mem-dog API.
* **2 read retries** — covers unexpected connection resets after the
  handshake succeeds.
* **Exponential backoff** — sleeps 0 s, 0.5 s, 1 s between attempts
  (``backoff_factor=0.5``).
* **Status-code retry** — automatically retries on 429 and 5xx gateway
  errors (502, 503, 504) for idempotent methods.
* Both HTTPS and HTTP adapters use the same policy so local development
  against ``http://localhost:8080`` behaves identically.
"""

import logging

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import MEM_DOG_API_KEY

logger = logging.getLogger("mem_dog.webhook.api_client.session")

# ---------------------------------------------------------------------------
# Retry policy
# ---------------------------------------------------------------------------

_RETRY = Retry(
    total=3,
    connect=3,        # retries on SSL / TCP connect failures (incl. SSLEOFError)
    read=2,           # retries on read-timeout / connection-reset
    backoff_factor=0.5,  # 0 s → 0.5 s → 1 s between attempts
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=frozenset(["GET", "POST", "DELETE"]),
    raise_on_status=False,
)

# ---------------------------------------------------------------------------
# Shared session (module-level singleton)
# ---------------------------------------------------------------------------

_session: requests.Session = requests.Session()
_adapter = HTTPAdapter(max_retries=_RETRY)
_session.mount("https://", _adapter)
_session.mount("http://", _adapter)

if MEM_DOG_API_KEY:
    _session.headers["x-api-key"] = MEM_DOG_API_KEY

logger.debug(
    "HTTP session initialised | connect_retries=%d  read_retries=%d  backoff_factor=%.1f  api_key=%s",
    _RETRY.connect,
    _RETRY.read,
    _RETRY.backoff_factor,
    "set" if MEM_DOG_API_KEY else "not set",
)
