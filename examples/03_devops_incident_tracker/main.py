"""DevOps Incident Tracker -- mem-dog example.

Track system incidents from alert to resolution. Uses tracing memory,
webhooks, key-value store for state, and timeline queries.

Usage:
    export MEM_DOG_URL=http://localhost:8080
    export MEM_DOG_API_KEY=your-key
    python main.py
"""

import os
import json
import time
from datetime import datetime, timezone

from mem_dog_client import MemDog, MemDogClient

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = os.environ.get("MEM_DOG_URL", "http://localhost:8080")
API_KEY = os.environ.get("MEM_DOG_API_KEY", "")

# ---------------------------------------------------------------------------
# Sample data -- incident lifecycle
# ---------------------------------------------------------------------------

INCIDENT_ID = "INC-20260520-001"

# Simulated incident events, ordered chronologically
INCIDENT_EVENTS = [
    {
        "phase": "alert",
        "timestamp": "2026-05-20T02:13:00Z",
        "content": (
            "ALERT [P1] payment-service: Error rate exceeded 5% threshold. "
            "Current error rate: 12.3%. Affected endpoint: POST /api/payments/charge. "
            "Region: us-east-1. Triggered by PagerDuty rule 'payment-errors-critical'. "
            "On-call engineer: Alex Kim."
        ),
        "tags": ["alert", "p1", "payment-service", "us-east-1"],
        "memory_type": "tracing",
    },
    {
        "phase": "acknowledge",
        "timestamp": "2026-05-20T02:15:00Z",
        "content": (
            "ACK: Alex Kim acknowledged alert at 02:15 UTC. "
            "Initial investigation started. Checking Grafana dashboards "
            "and recent deployments."
        ),
        "tags": ["ack", "investigation", "payment-service"],
        "memory_type": "tracing",
    },
    {
        "phase": "investigate",
        "timestamp": "2026-05-20T02:22:00Z",
        "content": (
            "INVESTIGATION: Found correlation with deploy #4821 (payment-service v2.14.0) "
            "rolled out at 01:45 UTC. Deploy included database connection pool changes. "
            "Error logs show 'ConnectionPoolExhausted' exceptions. "
            "Database connections at 98% capacity (normal: 40-60%)."
        ),
        "tags": ["investigation", "root-cause", "deploy-4821", "database"],
        "memory_type": "tracing",
    },
    {
        "phase": "escalate",
        "timestamp": "2026-05-20T02:30:00Z",
        "content": (
            "ESCALATION: Paging database team lead (Jordan Lee). "
            "Error rate now at 18.7%. Customer-facing impact confirmed: "
            "payment failures affecting ~2,400 transactions/hour. "
            "Revenue impact estimated at $15K/hour."
        ),
        "tags": ["escalation", "p1", "customer-impact", "database-team"],
        "memory_type": "tracing",
    },
    {
        "phase": "mitigate",
        "timestamp": "2026-05-20T02:45:00Z",
        "content": (
            "MITIGATION: Rolling back deploy #4821. "
            "kubectl rollout undo deployment/payment-service -n production. "
            "Rollback to v2.13.2 initiated. Additionally, scaling up "
            "database read replicas from 2 to 4 as a safety measure."
        ),
        "tags": ["mitigation", "rollback", "deploy-4821", "scaling"],
        "memory_type": "tracing",
    },
    {
        "phase": "monitor",
        "timestamp": "2026-05-20T03:00:00Z",
        "content": (
            "MONITORING: Rollback complete. Error rate dropping: "
            "18.7% -> 8.2% -> 3.1%. Database connections normalizing "
            "at 52%. Payment success rate recovering. "
            "Keeping extra read replicas for now."
        ),
        "tags": ["monitoring", "recovery", "metrics"],
        "memory_type": "tracing",
    },
    {
        "phase": "resolve",
        "timestamp": "2026-05-20T03:30:00Z",
        "content": (
            "RESOLVED: Error rate below 0.5% threshold for 30 minutes. "
            "All systems nominal. Total incident duration: 1h 17m. "
            "Affected transactions: ~4,800. Failed payments: ~1,200. "
            "Customer refunds to be processed by finance team. "
            "Post-mortem scheduled for 2026-05-21 10:00 UTC."
        ),
        "tags": ["resolved", "metrics", "post-mortem"],
        "memory_type": "timeline",
    },
]

# Post-mortem summary
POST_MORTEM = (
    "POST-MORTEM: INC-20260520-001 -- Payment Service Outage\n\n"
    "Root cause: Deploy #4821 (v2.14.0) changed the database connection pool "
    "from a shared pool to per-request connections, causing connection exhaustion "
    "under load. The change was not load-tested before deployment.\n\n"
    "Timeline: Alert at 02:13, ack at 02:15, root cause at 02:22, "
    "rollback at 02:45, resolved at 03:30. Total: 1h 17m.\n\n"
    "Action items:\n"
    "1. Add load testing to CI/CD pipeline for connection pool changes.\n"
    "2. Set database connection alerts at 70% capacity (currently 90%).\n"
    "3. Implement canary deployments for payment-service.\n"
    "4. Add circuit breaker for database connections.\n"
    "5. Process $18,000 in customer refunds."
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}\n")


def extract_id(response, key="data_id"):
    data = response.json()
    return data.get(key) or data.get("id")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Main workflow
# ---------------------------------------------------------------------------

def log_incident_events(m: MemDog) -> list[str]:
    """Record incident lifecycle events as tracing and timeline memories."""
    section("1. Recording Incident Events")
    data_ids = []
    for event in INCIDENT_EVENTS:
        result = m.add(
            event["content"],
            name=f"{INCIDENT_ID} - {event['phase'].upper()}",
            memory_type=event["memory_type"],
            tags=event["tags"],
        )
        did = result["data_id"]
        data_ids.append(did)
        print(f"  [{event['timestamp']}] {event['phase'].upper():<12} -> {did}")
    print(f"\n  Total events logged: {len(data_ids)}")
    return data_ids


def manage_incident_state(client: MemDogClient) -> None:
    """Use the key-value store to track incident state."""
    section("2. Incident State Management (Key-Value Store)")

    # Set initial incident state
    incident_key = f"incident:{INCIDENT_ID}"
    initial_state = {
        "incident_id": INCIDENT_ID,
        "status": "open",
        "severity": "P1",
        "service": "payment-service",
        "region": "us-east-1",
        "oncall": "Alex Kim",
        "opened_at": "2026-05-20T02:13:00Z",
        "last_updated": now_iso(),
    }

    print(f"  Setting state for {incident_key}...")
    try:
        resp = client.set_store_value(incident_key, initial_state)
        resp.raise_for_status()
        print(f"    Status: {initial_state['status']}, Severity: {initial_state['severity']}")
    except Exception as exc:
        print(f"    (error: {exc})")

    # Update state through phases
    state_updates = [
        {"status": "investigating", "assigned_to": ["Alex Kim", "Jordan Lee"]},
        {"status": "mitigating", "mitigation": "rollback deploy #4821"},
        {"status": "monitoring", "error_rate": "3.1%"},
        {"status": "resolved", "resolved_at": "2026-05-20T03:30:00Z", "duration_minutes": 77},
    ]
    for update in state_updates:
        merged = {**initial_state, **update, "last_updated": now_iso()}
        try:
            resp = client.set_store_value(incident_key, merged)
            resp.raise_for_status()
            print(f"    Updated -> status={update['status']}")
        except Exception as exc:
            print(f"    (error updating to {update['status']}: {exc})")

    # Read back final state
    print(f"\n  Reading final state for {incident_key}...")
    try:
        resp = client.get_store_value(incident_key)
        resp.raise_for_status()
        state = resp.json()
        print(f"    Status:    {state.get('status', '?')}")
        print(f"    Duration:  {state.get('duration_minutes', '?')} minutes")
        print(f"    Resolved:  {state.get('resolved_at', '?')}")
    except Exception as exc:
        print(f"    (error: {exc})")

    # List all incident keys
    print("\n  Listing all incident keys...")
    try:
        resp = client.list_store_keys(prefix="incident:")
        resp.raise_for_status()
        keys = resp.json()
        items = keys if isinstance(keys, list) else keys.get("keys", keys.get("items", []))
        for k in items:
            name = k if isinstance(k, str) else k.get("key", k)
            print(f"    - {name}")
        if not items:
            print("    (no keys found -- store may organize differently)")
    except Exception as exc:
        print(f"    (error: {exc})")


def setup_webhooks(client: MemDogClient) -> str:
    """Create and inspect a webhook for GitHub deploy events."""
    section("3. Webhook Management")

    # Create a webhook endpoint
    print("  Creating GitHub deploy webhook...")
    webhook_id = None
    try:
        resp = client.create_webhook({
            "name": "github-deploys",
            "channel_type": "github",
            "description": "Captures deploy events from payment-service repo",
            "events": ["deployment", "deployment_status"],
        })
        resp.raise_for_status()
        data = resp.json()
        webhook_id = data.get("webhook_id") or data.get("id")
        endpoint = data.get("endpoint_url", data.get("url", "N/A"))
        print(f"    Webhook ID: {webhook_id}")
        print(f"    Endpoint:   {endpoint}")
    except Exception as exc:
        print(f"    (error: {exc})")

    # List all webhooks
    print("\n  Listing webhooks...")
    try:
        resp = client.list_webhooks()
        resp.raise_for_status()
        webhooks = resp.json()
        items = webhooks if isinstance(webhooks, list) else webhooks.get("webhooks", webhooks.get("items", []))
        for wh in items[:5]:
            wid = wh.get("webhook_id", wh.get("id", "?"))
            name = wh.get("name", "?")
            status = wh.get("status", "?")
            print(f"    [{wid}] {name} (status={status})")
    except Exception as exc:
        print(f"    (error: {exc})")

    # Get webhook stats
    if webhook_id:
        print(f"\n  Webhook stats for {webhook_id}...")
        try:
            resp = client.get_webhook_stats(webhook_id)
            resp.raise_for_status()
            stats = resp.json()
            print(f"    Total events:  {stats.get('total_events', 0)}")
            print(f"    Success rate:  {stats.get('success_rate', 'N/A')}")
            print(f"    Last event:    {stats.get('last_event_at', 'none')}")
        except Exception as exc:
            print(f"    (error: {exc})")

    return webhook_id or ""


def store_post_mortem(m: MemDog) -> str:
    """Store the post-mortem as a timeline entry."""
    section("4. Storing Post-Mortem Report")
    result = m.add(
        POST_MORTEM,
        name=f"Post-Mortem: {INCIDENT_ID}",
        memory_type="timeline",
        tags=["post-mortem", "payment-service", "p1", INCIDENT_ID.lower()],
    )
    did = result["data_id"]
    print(f"  Stored post-mortem: {did}")
    return did


def run_post_mortem_analysis(client: MemDogClient) -> None:
    """Use RAG chat to analyze the incident for patterns."""
    section("5. AI Post-Mortem Analysis (RAG Chat)")
    queries = [
        "What was the root cause of the payment service outage?",
        "How long did it take to identify the root cause after the alert?",
        "What action items came out of the incident?",
    ]

    history = []
    for query in queries:
        print(f"  Q: {query}")
        try:
            resp = client.chat(
                query,
                search_mode="hybrid",
                conversation_history=history,
            )
            resp.raise_for_status()
            data = resp.json()
            answer = data.get("response", data.get("answer", str(data)))
            if isinstance(answer, str):
                preview = answer[:300] + ("..." if len(answer) > 300 else "")
                print(f"  A: {preview}")
            else:
                print(f"  A: {answer}")

            # Maintain conversation context
            history.append({"role": "user", "content": query})
            history.append({"role": "assistant", "content": str(answer)[:500]})
        except Exception as exc:
            print(f"  A: (error: {exc})")
        print()


def retrieve_and_display(m: MemDog, data_id: str) -> None:
    """Retrieve a single incident event for display."""
    section("6. Retrieving Single Event")
    print(f"  Fetching {data_id}...")
    try:
        item = m.get(data_id)
        print(f"  Name:    {item.get('name', 'N/A')}")
        print(f"  Tags:    {item.get('tags', [])}")
        content = item.get("content", "")
        if isinstance(content, str):
            print(f"  Content: {content[:200]}...")
        else:
            print(f"  Content: {str(content)[:200]}")
    except Exception as exc:
        print(f"  (error: {exc})")


def cleanup_webhook(client: MemDogClient, webhook_id: str) -> None:
    """Delete the test webhook."""
    section("7. Cleanup")
    if webhook_id:
        print(f"  Deleting webhook {webhook_id}...")
        try:
            resp = client.delete_webhook(webhook_id)
            resp.raise_for_status()
            print("    Deleted.")
        except Exception as exc:
            print(f"    (error: {exc})")

    # Clean up store key
    print(f"  Deleting store key incident:{INCIDENT_ID}...")
    try:
        resp = client.delete_store_value(f"incident:{INCIDENT_ID}")
        resp.raise_for_status()
        print("    Deleted.")
    except Exception as exc:
        print(f"    (error: {exc})")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Run the DevOps incident tracker demo."""
    print("DevOps Incident Tracker -- mem-dog Example")
    print(f"API: {BASE_URL}")

    if not API_KEY:
        print("\nWARNING: MEM_DOG_API_KEY not set. Requests may fail.\n")

    # Initialize both facade and full client
    m = MemDog(BASE_URL, api_key=API_KEY)
    client = m.client  # access underlying MemDogClient

    # Step 1: Log incident events
    data_ids = log_incident_events(m)

    # Step 2: Track state via key-value store
    manage_incident_state(client)

    # Step 3: Set up webhooks
    webhook_id = setup_webhooks(client)

    # Step 4: Store post-mortem
    pm_id = store_post_mortem(m)

    # Wait for embeddings
    print("\n  Waiting 2s for embedding generation...")
    time.sleep(2)

    # Step 5: AI analysis of the incident
    run_post_mortem_analysis(client)

    # Step 6: Retrieve single event
    if data_ids:
        retrieve_and_display(m, data_ids[2])  # investigation phase

    # Step 7: Cleanup
    cleanup_webhook(client, webhook_id)

    print("\nDone.")


if __name__ == "__main__":
    main()
