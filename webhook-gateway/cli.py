#!/usr/bin/env python3
"""Webhook Gateway CLI — manage channels, send messages, and check status.

Usage:
    python cli.py status
    python cli.py channels
    python cli.py providers
    python cli.py send <channel> <message>
    python cli.py send <channel> --file <path>
    python cli.py test <channel>
    python cli.py whatsapp-setup
    python cli.py telegram-setup <bot_token>

Environment variables:
    WGW_URL      Gateway URL (default: http://localhost:8080)
    WGW_API_KEY  API key (optional)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlencode

try:
    import httpx
except ImportError:
    print("httpx not installed. Run: uv pip install httpx")
    sys.exit(1)


def _url() -> str:
    return os.getenv("WGW_URL", "http://localhost:8080").rstrip("/")


def _headers() -> dict[str, str]:
    h: dict[str, str] = {"Content-Type": "application/json"}
    key = os.getenv("WGW_API_KEY", "")
    if key:
        h["x-api-key"] = key
    return h


def _print_json(data: dict) -> None:
    print(json.dumps(data, indent=2))


def _get(path: str) -> dict:
    resp = httpx.get(f"{_url()}{path}", headers=_headers(), timeout=10)
    resp.raise_for_status()
    return resp.json()


def _post(path: str, payload: dict) -> dict:
    resp = httpx.post(f"{_url()}{path}", json=payload, headers=_headers(), timeout=30)
    resp.raise_for_status()
    return resp.json()


CHANNELS = [
    "generic", "email", "video",
    "telegram", "slack", "discord", "whatsapp", "msteams", "webchat",
    "openclaw", "signal", "matrix", "irc", "googlechat", "line",
    "feishu", "mattermost", "nextcloud-talk", "nostr", "tlon",
    "twitch", "zalo", "bluebubbles", "imessage", "synology-chat",
]


def cmd_status(_args: argparse.Namespace) -> None:
    """Show gateway health and readiness."""
    print(f"Gateway: {_url()}\n")
    try:
        health = _get("/health")
        print(f"Health:  {health.get('status', 'unknown')}")
    except Exception as e:
        print(f"Health:  UNREACHABLE ({e})")
        return

    try:
        ready = _get("/ready")
        print(f"Ready:   {ready.get('status', 'unknown')}")
        checks = ready.get("checks", {})
        for k, v in checks.items():
            icon = "✅" if v else "❌"
            print(f"  {icon} {k}")
    except Exception as e:
        print(f"Ready:   error ({e})")

    try:
        info = _get("/providers/active")
        print(f"\nLLM:     {info.get('provider', 'none')} / {info.get('model', 'none')}")
    except Exception:
        print("\nLLM:     not configured")


def cmd_channels(_args: argparse.Namespace) -> None:
    """List all supported channels."""
    print("Supported channels:\n")
    print(f"{'Channel':<20} {'Endpoint'}")
    print(f"{'─' * 20} {'─' * 35}")
    for ch in CHANNELS:
        print(f"{ch:<20} /webhooks/{ch}")
    print(f"\n{len(CHANNELS)} channels total")
    print(f"\nWebhook URL pattern: {_url()}/webhooks/<channel>")
    key = os.getenv("WGW_API_KEY", "")
    if key:
        print(f"With API key:        {_url()}/webhooks/<channel>?api_key=<key>")


def cmd_providers(_args: argparse.Namespace) -> None:
    """Show LLM provider configuration."""
    try:
        data = _get("/providers")
        _print_json(data)
    except Exception as e:
        print(f"Error: {e}")


def cmd_send(args: argparse.Namespace) -> None:
    """Send a message to a channel."""
    channel = args.channel
    if channel not in CHANNELS:
        print(f"Unknown channel: {channel}")
        print(f"Available: {', '.join(CHANNELS)}")
        sys.exit(1)

    payload: dict = {
        "user_id": os.getenv("USER", "cli-user"),
        "channel_id": f"cli-{channel}",
    }

    if args.file:
        path = Path(args.file)
        if not path.exists():
            print(f"File not found: {args.file}")
            sys.exit(1)
        payload["text"] = args.message or f"[file: {path.name}]"
        payload["attachments"] = [{
            "name": path.name,
            "type": _guess_mime(path),
            "size": path.stat().st_size,
            "url": f"file://{path.resolve()}",
        }]
    else:
        if not args.message:
            print("Provide a message or --file")
            sys.exit(1)
        payload["text"] = args.message

    try:
        result = _post(f"/webhooks/{channel}", payload)
        print(f"✅ {result.get('status', 'ok')}")
        if result.get("trace_id"):
            print(f"   Trace ID:  {result['trace_id']}")
        if result.get("data_id"):
            print(f"   Data ID:   {result['data_id']}")
        if result.get("message_id"):
            print(f"   Message:   {result['message_id']}")
    except httpx.HTTPStatusError as e:
        print(f"❌ HTTP {e.response.status_code}: {e.response.text[:200]}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ {e}")
        sys.exit(1)


def cmd_test(args: argparse.Namespace) -> None:
    """Send a test message to a channel."""
    channel = args.channel
    args.message = f"Test message from CLI to {channel} at {__import__('datetime').datetime.now().isoformat()}"
    args.file = None
    cmd_send(args)


def cmd_whatsapp_setup(_args: argparse.Namespace) -> None:
    """Print WhatsApp webhook setup instructions."""
    base = _url()
    key = os.getenv("WGW_API_KEY", "")
    webhook_url = f"{base}/webhooks/whatsapp"
    if key:
        webhook_url += f"?api_key={key}"

    print("WhatsApp Business Setup")
    print("=" * 50)
    print()
    print("1. Go to https://developers.facebook.com/apps/")
    print("2. Create or select your app → add WhatsApp product")
    print("3. Go to WhatsApp > Configuration > Webhooks")
    print()
    print(f"   Callback URL:  {webhook_url}")
    print(f"   Verify token:  any-string-you-choose")
    print()
    print("4. Subscribe to: messages, message_status")
    print()
    print("5. Test with curl:")
    print()
    headers = '-H "Content-Type: application/json"'
    if key:
        headers += f' -H "x-api-key: {key}"'
    print(f'   curl -X POST {base}/webhooks/whatsapp \\')
    print(f'     {headers} \\')
    print(f'     -d \'{{"object":"whatsapp_business_account","entry":[{{"changes":[{{"value":{{"messages":[{{"from":"15551234567","type":"text","text":{{"body":"Hello!"}},"id":"wamid.test","timestamp":"1709136000"}}],"contacts":[{{"wa_id":"15551234567","profile":{{"name":"Test"}}}}],"metadata":{{"phone_number_id":"123"}}}},"field":"messages"}}]}}]}}\'')


def cmd_telegram_setup(args: argparse.Namespace) -> None:
    """Set Telegram bot webhook to point at the gateway."""
    base = _url()
    key = os.getenv("WGW_API_KEY", "")
    webhook_url = f"{base}/webhooks/telegram"
    if key:
        webhook_url += f"?api_key={key}"

    token = args.bot_token

    print("Telegram Bot Setup")
    print("=" * 50)
    print()
    print(f"Webhook URL: {webhook_url}")
    print()

    if token:
        print("Setting webhook via Telegram API...")
        try:
            resp = httpx.post(
                f"https://api.telegram.org/bot{token}/setWebhook",
                json={"url": webhook_url},
                timeout=10,
            )
            result = resp.json()
            if result.get("ok"):
                print(f"✅ Webhook set: {result.get('description')}")
            else:
                print(f"❌ Failed: {result.get('description')}")
        except Exception as e:
            print(f"❌ Error: {e}")
    else:
        print("To set the webhook, run:")
        print(f"  python cli.py telegram-setup <BOT_TOKEN>")
        print()
        print("Or manually:")
        print(f"  curl https://api.telegram.org/bot<TOKEN>/setWebhook \\")
        print(f'    -d \'{{"url":"{webhook_url}"}}\'')


def _guess_mime(path: Path) -> str:
    suffix = path.suffix.lower()
    return {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
        ".gif": "image/gif", ".webp": "image/webp", ".pdf": "application/pdf",
        ".mp4": "video/mp4", ".mp3": "audio/mpeg", ".wav": "audio/wav",
        ".txt": "text/plain", ".json": "application/json",
    }.get(suffix, "application/octet-stream")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="wgw",
        description="Webhook Gateway CLI",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("status", help="Show gateway health and readiness")
    sub.add_parser("channels", help="List supported channels")
    sub.add_parser("providers", help="Show LLM provider info")

    p_send = sub.add_parser("send", help="Send a message to a channel")
    p_send.add_argument("channel", help="Channel type (e.g. whatsapp, telegram, generic)")
    p_send.add_argument("message", nargs="?", help="Message text")
    p_send.add_argument("--file", "-f", help="Attach a file")

    p_test = sub.add_parser("test", help="Send a test message")
    p_test.add_argument("channel", help="Channel type")

    sub.add_parser("whatsapp-setup", help="Print WhatsApp webhook setup instructions")

    p_tg = sub.add_parser("telegram-setup", help="Set Telegram bot webhook")
    p_tg.add_argument("bot_token", nargs="?", help="Telegram bot token from @BotFather")

    args = parser.parse_args()

    commands = {
        "status": cmd_status,
        "channels": cmd_channels,
        "providers": cmd_providers,
        "send": cmd_send,
        "test": cmd_test,
        "whatsapp-setup": cmd_whatsapp_setup,
        "telegram-setup": cmd_telegram_setup,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
