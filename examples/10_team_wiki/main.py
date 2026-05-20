"""Team Wiki with Memory Lifecycle -- mem-dog example.

Complete data lifecycle: onboard users, ingest knowledge across
memory types, compress stale memories, export data, bulk cleanup.

Usage:
    export MEM_DOG_URL=http://localhost:8080
    export MEM_DOG_API_KEY=your-key
    python main.py
"""

import os
import json
from datetime import datetime

from mem_dog_client import MemDog, MemDogClient

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = os.environ.get("MEM_DOG_URL", "http://localhost:8080")
API_KEY = os.environ.get("MEM_DOG_API_KEY", "")

# ---------------------------------------------------------------------------
# Sample data: 2 users, 15 wiki entries across 5 memory types
# ---------------------------------------------------------------------------

USERS = [
    {"username": "alice", "email": "alice@example.com", "display_name": "Alice Chen"},
    {"username": "bob", "email": "bob@example.com", "display_name": "Bob Martinez"},
]

# 15 wiki entries organized by memory type (3 per type)
WIKI_ENTRIES = {
    "session": [
        {
            "name": "Sprint 42 Standup Notes",
            "content": "Sprint 42 standup (2025-05-19): Alice completed auth refactor. "
                       "Bob is blocked on API rate limiting. Action: Alice to review "
                       "Bob's PR by EOD. Carry-over: dashboard redesign.",
            "tags": ["standup", "sprint-42"],
            "user": "alice",
        },
        {
            "name": "Architecture Review Session",
            "content": "Reviewed proposed microservices migration. Decision: keep monolith "
                       "for core API, extract webhook processing to separate service. "
                       "Timeline: Q3 2025. Owner: Bob.",
            "tags": ["architecture", "review"],
            "user": "bob",
        },
        {
            "name": "Incident Postmortem - API Outage",
            "content": "Outage 2025-05-15 13:00-14:30 UTC. Root cause: connection pool "
                       "exhaustion from leaked DB connections. Fix: added connection "
                       "timeout and health checks. Follow-up: monitor p99 latency.",
            "tags": ["postmortem", "incident"],
            "user": "alice",
        },
    ],
    "conversation": [
        {
            "name": "Onboarding Q&A with New Hire",
            "content": "Q: Where do I find the deployment runbook? A: See docs/deployment/ "
                       "in the repo. Q: How do I get staging access? A: Request via IT "
                       "ticket, requires manager approval. Q: What is the PR review SLA? "
                       "A: 24 hours for standard PRs, 4 hours for hotfixes.",
            "tags": ["onboarding", "qa"],
            "user": "alice",
        },
        {
            "name": "Customer Escalation Discussion",
            "content": "Globex Corp reported data sync delays. Investigated: the webhook "
                       "queue had 50k backlog. Increased worker count from 3 to 10. "
                       "Resolution time: 45 minutes. Customer satisfied after follow-up.",
            "tags": ["escalation", "customer"],
            "user": "bob",
        },
        {
            "name": "Product Feedback Collection",
            "content": "Users want: (1) dark mode, (2) keyboard shortcuts, (3) bulk "
                       "export, (4) API pagination improvements. Priority from PM: "
                       "keyboard shortcuts first, then bulk export.",
            "tags": ["feedback", "product"],
            "user": "alice",
        },
    ],
    "organizational": [
        {
            "name": "Engineering Team Charter",
            "content": "Mission: Build reliable, scalable systems that delight users. "
                       "Values: Ship fast, measure everything, blameless postmortems. "
                       "Process: 2-week sprints, PR reviews, Friday demos.",
            "tags": ["charter", "team"],
            "user": "alice",
        },
        {
            "name": "On-Call Rotation Policy",
            "content": "Rotation: weekly, Mon 9am to Mon 9am. Primary and secondary "
                       "on-call. Response SLA: P1 = 15 min, P2 = 1 hour, P3 = next "
                       "business day. Compensation: 1 day off per week of on-call.",
            "tags": ["policy", "oncall"],
            "user": "bob",
        },
        {
            "name": "Vendor Access Policy",
            "content": "All vendor access requires SOC2 review. Approved vendors: AWS, "
                       "GCP, Datadog, PagerDuty, Slack, GitHub. New vendor requests go "
                       "through security review (2-week SLA). Annual re-certification.",
            "tags": ["policy", "security", "vendors"],
            "user": "alice",
        },
    ],
    "semantic": [
        {
            "name": "REST API Design Guidelines",
            "content": "Use plural nouns for resources (/users, /items). Version via URL "
                       "prefix (/api/v1/). Pagination: cursor-based with limit param. "
                       "Errors: RFC 7807 Problem Details. Auth: Bearer tokens in header.",
            "tags": ["guidelines", "api-design"],
            "user": "bob",
        },
        {
            "name": "Database Schema Conventions",
            "content": "Tables: snake_case plural (users, data_items). Primary keys: "
                       "ULID stored as text. Timestamps: created_at, updated_at with "
                       "timezone. Soft deletes: deleted_at column. Indexes on all FK cols.",
            "tags": ["guidelines", "database"],
            "user": "alice",
        },
        {
            "name": "Git Workflow Standards",
            "content": "Branching: main (production), develop (staging), feature/* "
                       "(work). Commits: conventional commits (feat:, fix:, chore:). "
                       "Merges: squash-merge to main. Tags: semver (v1.2.3). "
                       "CI: required passing before merge.",
            "tags": ["guidelines", "git"],
            "user": "bob",
        },
    ],
    "custom": [
        {
            "name": "Office Snack Inventory",
            "content": "Restocked 2025-05-19: granola bars (48), sparkling water (96), "
                       "coffee pods (120), almonds (24 bags), dried mango (12). "
                       "Budget remaining: $340 of $500 monthly allocation.",
            "tags": ["office", "snacks"],
            "user": "bob",
        },
        {
            "name": "Team Book Club - Current Read",
            "content": "Current: 'Designing Data-Intensive Applications' by Kleppmann. "
                       "Next meeting: Friday May 23, chapters 7-8. Previous: 'Staff "
                       "Engineer' by Larson (completed April). Upcoming: 'Observability "
                       "Engineering' by Majors.",
            "tags": ["bookclub", "team"],
            "user": "alice",
        },
        {
            "name": "Conference Travel Budget",
            "content": "2025 budget: $15,000 per engineer. Used: Alice $4,200 (KubeCon), "
                       "Bob $2,800 (PyCon). Remaining: Alice $10,800, Bob $12,200. "
                       "Upcoming: GopherCon (July, est. $3,500), re:Invent (Dec, $5,000).",
            "tags": ["budget", "travel", "conference"],
            "user": "bob",
        },
    ],
}


def onboard_users(client: MemDogClient) -> dict[str, str]:
    """Create users and generate API keys."""
    print("=" * 60)
    print("STEP 1: Onboarding Users")
    print("=" * 60)

    user_ids = {}
    for user in USERS:
        resp = client.create_user(user)
        resp.raise_for_status()
        data = resp.json()
        uid = data.get("user_id") or data.get("id")
        user_ids[user["username"]] = uid
        print(f"  Created user: {user['username']} ({user['email']}) -> {uid}")

        # Generate an API key for CLI access
        key_resp = client.create_api_key(uid, "cli")
        key_resp.raise_for_status()
        key_data = key_resp.json()
        api_key = key_data.get("api_key") or key_data.get("key", "md_***")
        print(f"    API key: {api_key[:12]}...")

    return user_ids


def ingest_wiki_entries(m: MemDog, user_ids: dict[str, str]) -> dict[str, list[dict]]:
    """Store 15 wiki entries across 5 memory types."""
    print("\n" + "=" * 60)
    print("STEP 2: Ingesting Wiki Entries (5 Memory Types)")
    print("=" * 60)

    all_results = {}  # memory_type -> list of {data_id, memory_id}

    for memory_type, entries in WIKI_ENTRIES.items():
        print(f"\n  -- {memory_type} (TTL varies) --")
        results = []

        for entry in entries:
            uid = user_ids.get(entry["user"])
            result = m.add(
                entry["content"],
                memory_type=memory_type,
                tags=entry["tags"],
                name=entry["name"],
                user_id=uid,
            )
            results.append(result)
            print(f"    [{entry['user']:5}] {entry['name'][:40]}...")
            print(f"           data_id={result['data_id']}, "
                  f"memory_id={result['memory_id']}")

        all_results[memory_type] = results

    total = sum(len(v) for v in all_results.values())
    print(f"\n  Total entries ingested: {total}")
    return all_results


def list_and_filter_memories(client: MemDogClient) -> None:
    """List memories with various filters."""
    print("\n" + "=" * 60)
    print("STEP 3: Listing Memories with Filters")
    print("=" * 60)

    # By memory type
    for mtype in ["session", "organizational", "semantic"]:
        resp = client.list_memories(memory_type=mtype)
        resp.raise_for_status()
        data = resp.json()
        items = data if isinstance(data, list) else data.get("items", [])
        print(f"  memory_type={mtype}: {len(items)} memories")

    # By category (Mem0 grouping)
    print()
    for category in ["conversation", "session", "user", "organizational"]:
        resp = client.list_memories(category=category)
        resp.raise_for_status()
        data = resp.json()
        items = data if isinstance(data, list) else data.get("items", [])
        print(f"  category={category}: {len(items)} memories")

    # Include expired
    print()
    resp = client.list_memories(include_expired=True, limit=50)
    resp.raise_for_status()
    data = resp.json()
    items = data if isinstance(data, list) else data.get("items", [])
    print(f"  include_expired=True: {len(items)} total memories")


def inspect_and_update_entries(client: MemDogClient, results: dict) -> None:
    """Get memory data, update item info."""
    print("\n" + "=" * 60)
    print("STEP 4: Inspecting and Updating Entries")
    print("=" * 60)

    # Pick the first organizational entry
    org_results = results.get("organizational", [])
    if not org_results:
        print("  No organizational entries to inspect.")
        return

    sample = org_results[0]
    mid = sample["memory_id"]
    did = sample["data_id"]

    # Get all data items in the memory
    print(f"\n  -- Data items in memory {mid} --")
    mem_data_resp = client.get_memory_data(mid)
    mem_data_resp.raise_for_status()
    mem_data = mem_data_resp.json()
    items = mem_data if isinstance(mem_data, list) else mem_data.get("items", [])
    print(f"  Items in memory: {len(items)}")
    for item in items[:5]:
        name = item.get("name", "untitled")
        print(f"    - {name} ({item.get('data_id', item.get('id', '?'))})")

    # Update the name and description of a data item
    print(f"\n  -- Updating info for {did} --")
    update_resp = client.update_info(
        did,
        name="Engineering Team Charter (v2)",
        description="Updated team charter with new mission statement and values.",
    )
    update_resp.raise_for_status()
    print(f"  Updated name and description")

    # Verify the update
    info_resp = client.get_info(did)
    info_resp.raise_for_status()
    info = info_resp.json()
    print(f"  Name: {info.get('name')}")
    print(f"  Description: {info.get('description')}")


def reorganize_memories(client: MemDogClient, results: dict) -> None:
    """Move data between memories for reorganization."""
    print("\n" + "=" * 60)
    print("STEP 5: Reorganizing Memories")
    print("=" * 60)

    session_results = results.get("session", [])
    if len(session_results) < 2:
        print("  Not enough session entries to demonstrate reorganization.")
        return

    # Remove the postmortem from session memory and re-link to organizational
    postmortem = session_results[2]  # "Incident Postmortem"
    session_mid = postmortem["memory_id"]
    postmortem_did = postmortem["data_id"]

    print(f"  Removing postmortem ({postmortem_did}) from session memory ({session_mid})")
    remove_resp = client.remove_data_from_memory(session_mid, postmortem_did)
    remove_resp.raise_for_status()
    print(f"  Removed successfully")

    # Add it to organizational memory instead
    org_results = results.get("organizational", [])
    if org_results:
        org_mid = org_results[0]["memory_id"]
        print(f"  Adding postmortem to organizational memory ({org_mid})")
        add_resp = client.add_data_to_memory(org_mid, [postmortem_did])
        add_resp.raise_for_status()
        print(f"  Added successfully -- postmortem now in organizational context")


def compress_stale_sessions(m: MemDog, results: dict) -> None:
    """Compress old session memories."""
    print("\n" + "=" * 60)
    print("STEP 6: Compressing Stale Sessions")
    print("=" * 60)

    session_results = results.get("session", [])
    if not session_results:
        print("  No session memories to compress.")
        return

    # Compress the session memory (standup notes are ephemeral)
    mid = session_results[0]["memory_id"]
    print(f"  Compressing session memory: {mid}")

    try:
        result = m.compress(
            mid,
            archive_originals=True,
            max_summary_length=500,
        )
        print(f"    Summary data_id: {result.get('summary_data_id')}")
        print(f"    Original count:  {result.get('original_count')}")
        print(f"    Summary length:  {result.get('summary_length')} chars")
        print(f"    Archived:        {result.get('archived')}")
    except Exception as e:
        print(f"    Compression result: {e}")


def export_user_data(client: MemDogClient) -> None:
    """Export all user data for GDPR compliance."""
    print("\n" + "=" * 60)
    print("STEP 7: GDPR Data Export")
    print("=" * 60)

    resp = client.dump_user_data()
    resp.raise_for_status()
    dump = resp.json()

    if isinstance(dump, dict):
        sections = list(dump.keys())
        print(f"  Export sections: {sections}")
        for section in sections[:5]:
            val = dump[section]
            if isinstance(val, list):
                print(f"    {section}: {len(val)} items")
            elif isinstance(val, dict):
                print(f"    {section}: {len(val)} keys")
            else:
                print(f"    {section}: {type(val).__name__}")
    elif isinstance(dump, list):
        print(f"  Export contains {len(dump)} records")

    print(f"\n  (In production, this would be packaged as a ZIP and sent to the user)")


def bulk_cleanup(client: MemDogClient, results: dict) -> None:
    """Bulk delete data and memories for cleanup."""
    print("\n" + "=" * 60)
    print("STEP 8: Bulk Cleanup")
    print("=" * 60)

    # Collect custom memory IDs and data IDs for cleanup
    custom_results = results.get("custom", [])
    if not custom_results:
        print("  No custom entries to clean up.")
        return

    data_ids = [r["data_id"] for r in custom_results if r.get("data_id")]
    memory_ids = list({r["memory_id"] for r in custom_results if r.get("memory_id")})

    # Bulk delete data items
    if data_ids:
        print(f"  Bulk deleting {len(data_ids)} data items...")
        resp = client.bulk_delete_data(data_ids)
        resp.raise_for_status()
        result = resp.json()
        print(f"    Result: {json.dumps(result)[:100]}")

    # Bulk delete memories
    if memory_ids:
        print(f"  Bulk deleting {len(memory_ids)} memories...")
        resp = client.bulk_delete_memories(memory_ids, delete_data=False)
        resp.raise_for_status()
        result = resp.json()
        print(f"    Result: {json.dumps(result)[:100]}")

    print(f"\n  Cleanup complete: {len(data_ids)} data items, "
          f"{len(memory_ids)} memories removed")


def main():
    """Run the team wiki lifecycle demo."""
    print("Team Wiki with Memory Lifecycle -- mem-dog Example")
    print(f"API: {BASE_URL}")
    print(f"Time: {datetime.now().isoformat()}")
    print()

    m = MemDog(BASE_URL, api_key=API_KEY)
    client = m.client

    # Step 1: Onboard users
    user_ids = onboard_users(client)

    # Step 2: Ingest wiki entries across memory types
    results = ingest_wiki_entries(m, user_ids)

    # Step 3: List and filter memories
    list_and_filter_memories(client)

    # Step 4: Inspect and update entries
    inspect_and_update_entries(client, results)

    # Step 5: Reorganize memories
    reorganize_memories(client, results)

    # Step 6: Compress stale sessions
    compress_stale_sessions(m, results)

    # Step 7: GDPR data export
    export_user_data(client)

    # Step 8: Bulk cleanup
    bulk_cleanup(client, results)

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Users onboarded:  {len(user_ids)}")
    total_entries = sum(len(v) for v in WIKI_ENTRIES.values())
    print(f"  Wiki entries:     {total_entries}")
    print(f"  Memory types:     {', '.join(WIKI_ENTRIES.keys())}")
    print(f"  Reorganized:      postmortem -> organizational")
    print(f"  Compressed:       session memories")
    print(f"  Exported:         GDPR user data dump")
    print(f"  Cleaned up:       custom entries bulk-deleted")
    print("\nDone.")


if __name__ == "__main__":
    main()
