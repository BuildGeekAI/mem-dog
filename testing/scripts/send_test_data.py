#!/usr/bin/env python3
"""send_test_data.py — Send test payloads to every sub-agent.

Sends one representative payload for each of the 26 agent types, either:

  --mode local     Call route_payload() directly (no server needed)
  --mode webhook   POST to the real webhook endpoint (needs API key)

The payloads are spread across a configurable "ramp curve" so you can
watch them flow through the system rather than hammering it at once.

Usage
-----
# Local (no infra required)
python testing/scripts/send_test_data.py --mode local

# Webhook endpoint
python testing/scripts/send_test_data.py \\
  --mode webhook \\
  --url https://YOUR-GATEWAY-URL/webhook \\
  --api-key YOUR_API_KEY

# Slow curve — add 0.5 s between requests
python testing/scripts/send_test_data.py --mode local --delay 0.5

# Target a specific group prefix so all test data lands in shared memories
python testing/scripts/send_test_data.py --mode local --prefix test-run-42

# Dry-run — print payloads without sending
python testing/scripts/send_test_data.py --mode local --dry-run

Exit codes: 0 = all passed, 1 = some failed, 2 = all failed.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from typing import Any, Optional

# ---------------------------------------------------------------------------
# All 26 test payloads — one per agent type
# ---------------------------------------------------------------------------

TEST_PAYLOADS: list[dict[str, Any]] = [
    # ── Media ──────────────────────────────────────────────────────────────
    {
        "description": "Live RTSP video stream",
        "data_type": "video_stream",
        "source": "rtsp://camera-01.example.com/live",
        "fps": 30,
        "resolution": "1920x1080",
        "user_id": "robot-01",
    },
    {
        "description": "MP4 video from CDN",
        "url": "https://cdn.example.com/uploads/promo-2026.mp4",
        "content_type": "video/mp4",
        "duration_seconds": 120,
        "user_id": "marketing",
    },
    {
        "description": "Live microphone stream",
        "data_type": "audio_stream",
        "source": "webrtc://meeting.example.com/room-42",
        "sample_rate": 44100,
        "user_id": "conferencing",
    },
    {
        "description": "Podcast episode",
        "url": "https://podcasts.example.com/ep-99.mp3",
        "content_type": "audio/mpeg",
        "title": "Episode 99: Memory Machines",
        "user_id": "alice",
    },
    {
        "description": "Product photo",
        "url": "https://media.example.com/products/widget-v2.jpg",
        "content_type": "image/jpeg",
        "alt_text": "Widget v2 — side view",
        "user_id": "ecommerce",
    },
    {
        "description": "Gallery of event photos",
        "data_type": "image_batch",
        "images": [
            "https://media.example.com/event/photo-01.jpg",
            "https://media.example.com/event/photo-02.jpg",
            "https://media.example.com/event/photo-03.jpg",
        ],
        "event": "quarterly-all-hands-2026",
        "user_id": "hr",
    },
    # ── Documents ──────────────────────────────────────────────────────────
    {
        "description": "Q1 financial report PDF",
        "url": "https://storage.example.com/reports/q1-2026.pdf",
        "content_type": "application/pdf",
        "title": "Q1 2026 Financial Report",
        "pages": 42,
        "user_id": "finance",
    },
    {
        "description": "Quarterly plan in Word",
        "url": "https://storage.example.com/docs/q2-plan.docx",
        "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "author": "Jane Smith",
        "user_id": "strategy",
    },
    {
        "description": "API documentation in Markdown",
        "url": "https://github.example.com/docs/api.md",
        "content_type": "text/markdown",
        "title": "API Reference v3",
        "user_id": "engineering",
    },
    {
        "description": "Homepage HTML",
        "url": "https://www.example.com/",
        "content_type": "text/html",
        "scraped_at": "2026-02-17T09:00:00Z",
        "user_id": "web-crawler",
    },
    # ── Structured data ────────────────────────────────────────────────────
    {
        "description": "Order confirmation JSON",
        "content_type": "application/json",
        "data": {
            "order_id": "ORD-9871",
            "customer": "alice@example.com",
            "total_usd": 149.99,
            "items": [{"sku": "WIDG-001", "qty": 2}],
        },
        "user_id": "orders",
    },
    {
        "description": "Config file in XML",
        "url": "https://config.example.com/service.xml",
        "content_type": "application/xml",
        "schema": "service-config-v2",
        "user_id": "ops",
    },
    {
        "description": "Sales data CSV",
        "url": "https://reports.example.com/sales-jan-2026.csv",
        "content_type": "text/csv",
        "rows": 15000,
        "columns": ["date", "product", "region", "revenue"],
        "user_id": "analytics",
    },
    {
        "description": "Kubernetes manifest YAML",
        "url": "https://git.example.com/infra/deployment.yaml",
        "content_type": "application/yaml",
        "resource_kind": "Deployment",
        "user_id": "platform",
    },
    # ── Code & Logs ────────────────────────────────────────────────────────
    {
        "description": "Python diff / patch",
        "data_type": "code",
        "url": "https://github.example.com/prs/42.diff",
        "language": "python",
        "lines_changed": 87,
        "user_id": "dev-alice",
    },
    {
        "description": "Live application log stream",
        "data_type": "log_stream",
        "source": "k8s://namespace/pod-abc123",
        "service": "api-server",
        "log_level": "ERROR",
        "user_id": "sre",
    },
    {
        "description": "Archived log file",
        "url": "https://logs.example.com/api-2026-02-17.log",
        "content_type": "text/x-log",
        "size_mb": 45,
        "user_id": "sre",
    },
    # ── Sensor / IoT ───────────────────────────────────────────────────────
    {
        "description": "Warehouse temperature sensor",
        "data_type": "sensor",
        "device_id": "TEMP-WH-007",
        "readings": {"temperature_c": 4.2, "humidity_pct": 62},
        "timestamp": "2026-02-17T08:30:00Z",
        "user_id": "warehouse-ops",
    },
    {
        "description": "Fleet vehicle GPS track",
        "data_type": "gps",
        "vehicle_id": "VAN-14",
        "coordinates": [
            {"lat": 37.7749, "lon": -122.4194, "ts": "2026-02-17T08:00:00Z"},
            {"lat": 37.7751, "lon": -122.4189, "ts": "2026-02-17T08:01:00Z"},
        ],
        "user_id": "fleet",
    },
    {
        "description": "Smartwatch biometric data",
        "data_type": "biometric",
        "device_id": "WATCH-ALICE-001",
        "heart_rate_bpm": 72,
        "steps_today": 8412,
        "user_id": "alice",
    },
    # ── Spatial / 3D ───────────────────────────────────────────────────────
    {
        "description": "Warehouse LiDAR scan",
        "data_type": "lidar",
        "url": "https://storage.example.com/scans/warehouse-2026-02-17.pcd",
        "scanner": "Velodyne HDL-64E",
        "points": 131072,
        "user_id": "robotics",
    },
    {
        "description": "City boundary GeoJSON",
        "url": "https://geo.example.com/cities/sf-boundary.geojson",
        "content_type": "application/geo+json",
        "feature_count": 1,
        "user_id": "mapping",
    },
    {
        "description": "Product 3D model",
        "url": "https://assets.example.com/models/widget-v2.gltf",
        "content_type": "model/gltf+json",
        "polygon_count": 24000,
        "user_id": "design",
    },
    # ── Communication & Web ────────────────────────────────────────────────
    {
        "description": "Support email thread",
        "data_type": "email",
        "from": "support@example.com",
        "to": "alice@example.com",
        "subject": "Re: Order ORD-9871 issue",
        "received_at": "2026-02-17T10:15:00Z",
        "user_id": "support",
    },
    {
        "description": "Slack channel export",
        "data_type": "chat",
        "platform": "slack",
        "channel": "#engineering",
        "message_count": 342,
        "exported_at": "2026-02-17T00:00:00Z",
        "user_id": "dev-ops",
    },
    {
        "description": "Team calendar events",
        "url": "https://calendar.example.com/team.ics",
        "content_type": "text/calendar",
        "event_count": 12,
        "user_id": "hr",
    },
    {
        "description": "Scraped product page",
        "data_type": "web_page",
        "url": "https://shop.example.com/products/widget-v2",
        "title": "Widget v2 — Shop",
        "scraped_at": "2026-02-17T07:00:00Z",
        "user_id": "price-monitor",
    },
    {
        "description": "Tech blog RSS feed",
        "url": "https://techblog.example.com/rss.xml",
        "content_type": "application/rss+xml",
        "item_count": 20,
        "user_id": "research",
    },
    # ── Binary / Scientific ────────────────────────────────────────────────
    {
        "description": "Model checkpoint archive",
        "url": "https://ml.example.com/checkpoints/model-v3.tar.gz",
        "content_type": "application/x-tar",
        "size_mb": 512,
        "user_id": "ml-team",
    },
    {
        "description": "Server metrics time series",
        "data_type": "time_series",
        "metric": "cpu_utilisation_pct",
        "interval_seconds": 60,
        "data_points": [
            {"ts": "2026-02-17T08:00:00Z", "value": 42.1},
            {"ts": "2026-02-17T08:01:00Z", "value": 38.7},
            {"ts": "2026-02-17T08:02:00Z", "value": 51.3},
        ],
        "user_id": "sre",
    },
    {
        "description": "DICOM MRI scan",
        "url": "https://radiology.example.com/studies/P001-brain.dcm",
        "content_type": "application/dicom",
        "study_date": "2026-02-17",
        "modality": "MRI",
        "user_id": "radiology",
    },
    {
        "description": "Unknown binary — fallback test",
        "raw_bytes": "AQIDBA==",
        "origin": "mystery-device",
        "user_id": "lab",
    },
]


# ---------------------------------------------------------------------------
# Result tracking
# ---------------------------------------------------------------------------

@dataclass
class Result:
    index: int
    description: str
    expected_type: Optional[str]
    actual_type: Optional[str]
    is_new_group: Optional[bool]
    group_timeline: Optional[str]
    status: str   # "pass" | "fail" | "dry-run"
    error: Optional[str] = None
    elapsed_ms: float = 0.0


# ---------------------------------------------------------------------------
# Local mode
# ---------------------------------------------------------------------------

def send_local(payload: dict, prefix: Optional[str]) -> dict:
    """Call route_payload() directly without any HTTP."""
    import sys
    import os

    # Resolve the webhook/processor directory from multiple possible starting points
    candidates = []

    # 1. Relative to this script file
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        candidates.append(os.path.join(script_dir, "..", "..", "webhook", "processor"))
    except NameError:
        pass  # __file__ not set (e.g. exec() context)

    # 2. Relative to cwd
    for up in (".", "..", "../..", "../../.."):
        candidates.append(os.path.join(up, "webhook", "processor"))

    for candidate in candidates:
        abs_path = os.path.abspath(candidate)
        if os.path.isdir(os.path.join(abs_path, "webhook_agent")):
            if abs_path not in sys.path:
                sys.path.insert(0, abs_path)
            break

    from webhook_agent.router import route_payload  # type: ignore

    if prefix:
        payload = {**payload, "memory_prefix": prefix}

    return route_payload(json.dumps(payload))


# ---------------------------------------------------------------------------
# Webhook mode
# ---------------------------------------------------------------------------

def send_webhook(
    payload: dict,
    url: str,
    api_key: str,
    prefix: Optional[str],
    timeout: int,
) -> dict:
    """POST payload to the real webhook endpoint and return parsed response."""
    import urllib.request

    if prefix:
        payload = {**payload, "memory_prefix": prefix}

    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read())
    return data


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------

PASS   = "\033[92m✓\033[0m"
FAIL   = "\033[91m✗\033[0m"
DRY    = "\033[94m○\033[0m"
WARN   = "\033[93m△\033[0m"
RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"


def _col(text: str, code: str) -> str:
    return f"{code}{text}{RESET}"


def print_header() -> None:
    print()
    print(f"{BOLD}{'─' * 72}{RESET}")
    print(f"{BOLD}  memdog · Agent Routing Test Suite  ({len(TEST_PAYLOADS)} payloads){RESET}")
    print(f"{BOLD}{'─' * 72}{RESET}")
    print()


def print_row(r: Result, verbose: bool = False) -> None:
    icon = {"pass": PASS, "fail": FAIL, "dry-run": DRY}.get(r.status, WARN)
    elapsed = f"{r.elapsed_ms:5.0f}ms" if r.elapsed_ms else "      "
    actual = r.actual_type or "—"

    type_col = _col(actual, "\033[96m") if r.status == "pass" else _col(actual or "error", "\033[91m")
    new_grp  = _col("new-group", "\033[93m") if r.is_new_group else ""

    print(f"  {icon}  {elapsed}  {type_col:<20}  {r.description[:42]:<44}  {new_grp}")

    if r.error and verbose:
        print(f"      {_col(r.error, chr(27) + '[91m')}")
    if r.group_timeline and verbose:
        print(f"      {DIM}group → {r.group_timeline}{RESET}")


def print_summary(results: list[Result]) -> None:
    passed   = sum(1 for r in results if r.status == "pass")
    failed   = sum(1 for r in results if r.status == "fail")
    dry_runs = sum(1 for r in results if r.status == "dry-run")
    total    = len(results)
    avg_ms   = (
        sum(r.elapsed_ms for r in results if r.elapsed_ms) / max(1, total - dry_runs)
    )

    print()
    print(f"{BOLD}{'─' * 72}{RESET}")
    print(f"  Passed    {_col(str(passed), chr(27) + '[92m')}/{total}")
    if failed:
        print(f"  Failed    {_col(str(failed), chr(27) + '[91m')}/{total}")
    if dry_runs:
        print(f"  Dry-run   {dry_runs}/{total}")
    if avg_ms:
        print(f"  Avg time  {avg_ms:.0f} ms / payload")
    print(f"{BOLD}{'─' * 72}{RESET}")
    print()

    if failed:
        print(f"{_col('Failed payloads:', chr(27) + '[91m')}")
        for r in results:
            if r.status == "fail":
                print(f"  [{r.index:02d}] {r.description}")
                if r.error:
                    print(f"       {_col(r.error, chr(27) + '[91m')}")
        print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(args: argparse.Namespace) -> int:
    print_header()

    if args.mode == "local":
        print(f"  Mode:    {_col('local', chr(27) + '[92m')} (route_payload() direct call)")
    else:
        print(f"  Mode:    {_col('webhook', chr(27) + '[93m')} → {args.url}")

    if args.prefix:
        print(f"  Prefix:  {_col(args.prefix, chr(27) + '[96m')} (all data → shared memories)")
    if args.delay:
        print(f"  Delay:   {args.delay}s between payloads (ramp curve)")
    if args.dry_run:
        print(f"  {_col('DRY RUN — payloads printed, nothing sent', chr(27) + '[94m')}")

    print()
    print(f"  {'TIME':>7}  {'TYPE':<20}  {'DESCRIPTION':<44}  GROUP")
    print(f"  {'─' * 68}")

    results: list[Result] = []

    for idx, payload in enumerate(TEST_PAYLOADS, start=1):
        desc = payload.get("description", f"payload-{idx}")
        expected = payload.get("data_type")  # may be None (MIME/URL routing)

        if args.dry_run:
            print(f"  {DRY}  {'—':>5}   {'(dry-run)':<20}  {desc[:44]}")
            if args.verbose:
                print(f"      {json.dumps({k: v for k, v in payload.items() if k != 'description'}, indent=2)}")
            results.append(Result(
                index=idx, description=desc, expected_type=expected,
                actual_type=None, is_new_group=None, group_timeline=None,
                status="dry-run",
            ))
            continue

        start = time.perf_counter()
        try:
            if args.mode == "local":
                response = send_local(payload, args.prefix)
            else:
                response = send_webhook(payload, args.url, args.api_key, args.prefix, args.timeout)

            elapsed = (time.perf_counter() - start) * 1000
            actual_type    = response.get("data_type")
            is_new_group   = response.get("is_new_group")
            group_timeline = response.get("group_timeline")

            results.append(Result(
                index=idx, description=desc, expected_type=expected,
                actual_type=actual_type, is_new_group=is_new_group,
                group_timeline=group_timeline,
                status="pass", elapsed_ms=elapsed,
            ))

        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            results.append(Result(
                index=idx, description=desc, expected_type=expected,
                actual_type=None, is_new_group=None, group_timeline=None,
                status="fail", error=str(exc), elapsed_ms=elapsed,
            ))

        print_row(results[-1], verbose=args.verbose)

        if args.delay and idx < len(TEST_PAYLOADS):
            time.sleep(args.delay)

    print_summary(results)

    failed = sum(1 for r in results if r.status == "fail")
    total  = sum(1 for r in results if r.status != "dry-run")

    if total == 0:
        return 0          # dry-run, nothing to report
    if failed == total:
        return 2          # all failed
    if failed > 0:
        return 1          # some failed
    return 0              # all passed


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Send test data to all 26 memdog sub-agents.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--mode",
        choices=["local", "webhook"],
        default="local",
        help="'local' calls route_payload() directly; 'webhook' POSTs to the endpoint",
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8080/webhook",
        help="Webhook endpoint URL (mode=webhook only)",
    )
    parser.add_argument(
        "--api-key",
        default="",
        dest="api_key",
        help="API key for x-api-key header (mode=webhook only)",
    )
    parser.add_argument(
        "--prefix",
        default=None,
        help="Optional memory_prefix to group all test data (e.g. 'test-run-42')",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.0,
        help="Seconds to wait between payloads — spreads load over time (default 0)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="HTTP timeout in seconds (mode=webhook only, default 30)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print payloads without sending anything",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print group timeline and error details for each payload",
    )
    parser.add_argument(
        "--filter",
        default=None,
        metavar="TYPE",
        help="Only send the payload for this agent type (e.g. 'pdf', 'lidar')",
    )

    args = parser.parse_args()

    # Apply --filter
    global TEST_PAYLOADS
    if args.filter:
        TEST_PAYLOADS = [
            p for p in TEST_PAYLOADS
            if p.get("data_type") == args.filter
            or p.get("content_type", "").startswith(args.filter)
        ]
        if not TEST_PAYLOADS:
            print(f"No payloads match --filter {args.filter!r}")
            sys.exit(1)

    sys.exit(run(args))


if __name__ == "__main__":
    main()
