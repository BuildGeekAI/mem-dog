"""Channel-level access policies.

Loaded from ``WGW_CHANNEL_CONFIG`` (JSON string) or
``WGW_CHANNEL_CONFIG_FILE`` (path to a JSON file).  Example:

    {
      "whatsapp": {
        "enabled": true,
        "allowFrom": ["+14087310242", "+15551234567"],
        "denyFrom": [],
        "dmPolicy": "pairing"
      },
      "telegram": {
        "enabled": true
      },
      "email": {
        "enabled": false
      }
    }

Policy rules:
- If a channel is not listed, it is **enabled by default** with no
  sender restrictions.
- ``enabled: false`` rejects all inbound webhooks for that channel.
- ``allowFrom`` (if non-empty) only permits the listed sender IDs
  (phone numbers, emails, user IDs — matched against ``peer_id``).
- ``denyFrom`` (if non-empty) blocks the listed sender IDs.
- ``denyFrom`` is checked before ``allowFrom``.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_log = logging.getLogger("webhook_gateway.channel_policy")


@dataclass
class ChannelPolicy:
    enabled: bool = True
    allow_from: list[str] = field(default_factory=list)
    deny_from: list[str] = field(default_factory=list)
    dm_policy: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


_policies: dict[str, ChannelPolicy] = {}
_loaded: bool = False


def _load() -> None:
    global _policies, _loaded
    if _loaded:
        return
    _loaded = True

    raw: dict[str, Any] = {}

    config_file = os.getenv("WGW_CHANNEL_CONFIG_FILE", "")
    if config_file:
        path = Path(config_file)
        if path.is_file():
            try:
                raw = json.loads(path.read_text())
                _log.info("Loaded channel config from %s (%d channels)", path, len(raw))
            except Exception as exc:
                _log.warning("Failed to load channel config file %s: %s", path, exc)

    config_json = os.getenv("WGW_CHANNEL_CONFIG", "")
    if config_json:
        try:
            raw = json.loads(config_json)
            _log.info("Loaded channel config from WGW_CHANNEL_CONFIG env (%d channels)", len(raw))
        except Exception as exc:
            _log.warning("Failed to parse WGW_CHANNEL_CONFIG: %s", exc)

    for ch, cfg in raw.items():
        if not isinstance(cfg, dict):
            continue
        _policies[ch] = ChannelPolicy(
            enabled=cfg.get("enabled", True),
            allow_from=[str(x) for x in cfg.get("allowFrom", [])],
            deny_from=[str(x) for x in cfg.get("denyFrom", [])],
            dm_policy=cfg.get("dmPolicy", ""),
            extra={k: v for k, v in cfg.items() if k not in ("enabled", "allowFrom", "denyFrom", "dmPolicy")},
        )


def get_policy(channel_type: str) -> ChannelPolicy:
    """Return the policy for a channel (default: enabled, no restrictions)."""
    _load()
    return _policies.get(channel_type, ChannelPolicy())


def check_access(channel_type: str, sender_id: str) -> str | None:
    """Check whether *sender_id* is allowed on *channel_type*.

    Returns ``None`` if access is permitted, or an error message string
    if the request should be rejected.
    """
    policy = get_policy(channel_type)

    if not policy.enabled:
        return f"Channel '{channel_type}' is disabled"

    if policy.deny_from and sender_id in policy.deny_from:
        return f"Sender '{sender_id}' is blocked on '{channel_type}'"

    if policy.allow_from and sender_id not in policy.allow_from:
        return f"Sender '{sender_id}' is not in the allowlist for '{channel_type}'"

    return None


def list_policies() -> dict[str, dict[str, Any]]:
    """Return all configured channel policies as a serializable dict."""
    _load()
    result: dict[str, dict[str, Any]] = {}
    for ch, p in _policies.items():
        result[ch] = {
            "enabled": p.enabled,
            "allowFrom": p.allow_from,
            "denyFrom": p.deny_from,
            "dmPolicy": p.dm_policy,
        }
        if p.extra:
            result[ch].update(p.extra)
    return result


def reload() -> None:
    """Force reload of channel config (useful for testing)."""
    global _loaded
    _loaded = False
    _policies.clear()
    _load()
