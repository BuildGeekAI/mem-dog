"""Technical Win Room -- mem-dog example.

Sales engineering knowledge for enterprise deals: POC notes, Slack, GitHub,
security questionnaires, and CRM context in one permissioned memory.

Usage:
    export MEM_DOG_URL=http://localhost:8080
    export MEM_DOG_API_KEY=your-key
    python main.py
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone

from mem_dog_client import MemDog, MemDogClient

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = os.environ.get("MEM_DOG_URL", "http://localhost:8080")
API_KEY = os.environ.get("MEM_DOG_API_KEY", "")

DEAL_ID = "deal-acme-corp"
DEAL_NAME = "Acme Corp - Enterprise Platform"

SEARCH_MODES = ["hybrid", "graph", "full"]

# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

SALES_ENGINEERS = [
    {
        "username": "mrodriguez",
        "display_name": "Maya Rodriguez",
        "email": "maya@acmesales.com",
        "role": "admin",
    },
    {
        "username": "jchen",
        "display_name": "Jordan Chen",
        "email": "jordan@acmesales.com",
        "role": "member",
    },
]

SE_PLAYBOOK = [
    {
        "name": "Playbook: Enterprise SSO (SAML/OIDC)",
        "content": (
            "Enterprise SSO Playbook\n\n"
            "Supported: SAML 2.0 and OIDC. Typical go-live: 2-3 weeks after "
            "IdP metadata exchange. Sandbox available in all regions. "
            "Common blockers: attribute mapping, MFA enforcement, "
            "SCIM provisioning scope. Escalate to platform-security@ for "
            "custom claim requirements."
        ),
        "tags": ["playbook", "sso", "security"],
    },
    {
        "name": "Playbook: Data Residency (EU)",
        "content": (
            "Data Residency Playbook\n\n"
            "EU tenant available (Frankfurt). All embeddings and metadata "
            "stay in-region; optional GCS bucket in eu-west-1 for raw binary. "
            "DPA template on file. SOC 2 Type II report covers EU controls."
        ),
        "tags": ["playbook", "compliance", "eu", "soc2"],
    },
    {
        "name": "Playbook: POC Load Testing Checklist",
        "content": (
            "POC Load Test Checklist\n\n"
            "Before load test: confirm connection pool limits, heap sizing, "
            "and replica count. Run ramp 1x → 5x → 10x expected RPS. "
            "Capture Grafana dashboard links in deal timeline. "
            "If OOM or pool exhaustion, file GitHub issue and tag #poc-blocker."
        ),
        "tags": ["playbook", "poc", "performance"],
    },
]

DEAL_ARTIFACTS = [
    {
        "channel": "slack",
        "name": "Slack #acme-war-room — SSO timeline",
        "content": (
            "[2026-05-08 14:22] Amanda Chen (Acme VP Eng): Can you commit to SSO "
            "in production by end of Q2? Our security team is blocking pilot "
            "until SAML is live.\n"
            "[2026-05-08 14:35] Maya Rodriguez: Sandbox SAML is ready today. "
            "Production SSO typically needs 2-3 weeks after IdP metadata — "
            "we can target June 30 if legal reviews DPA this week."
        ),
        "tags": ["slack", "acme", "sso", "commitment"],
    },
    {
        "channel": "github",
        "name": "GitHub issue #1842 — POC OOM under load",
        "content": (
            "Repository: acme-poc/mem-dog-integration\n"
            "Issue #1842: OOM during 10k RPS load test\n\n"
            "Repro: payment-sim workload, 10k RPS for 15 minutes. "
            "JVM heap exhausted; logs show ConnectionPoolExhausted. "
            "Deploy in POC used per-request DB connections (not shared pool). "
            "Assignee: Maya Rodriguez. Labels: poc-blocker, performance."
        ),
        "tags": ["github", "poc", "performance", "blocker", "acme"],
    },
    {
        "channel": "github",
        "name": "GitHub PR #89 — connection pool fix",
        "content": (
            "PR #89: Revert to shared connection pool in POC branch\n"
            "Merged 2026-05-12. Load test at 10k RPS passed for 30 minutes. "
            "Amanda Chen signed off on Slack. Remaining concern: EU data residency "
            "for embeddings — legal reviewing DPA."
        ),
        "tags": ["github", "poc", "resolved", "acme"],
    },
    {
        "channel": "gmail",
        "name": "Gmail — Security questionnaire (SOC2, SSO)",
        "content": (
            "From: security@acmecorp.com\n"
            "Subject: Vendor security assessment — mem-dog\n\n"
            "Please confirm: (1) SOC 2 Type II scope includes EU region, "
            "(2) SAML attribute mapping documentation, (3) encryption at rest "
            "for vector embeddings. Deadline: 2026-05-20."
        ),
        "tags": ["gmail", "security", "questionnaire", "acme"],
    },
    {
        "channel": "hubspot",
        "name": "HubSpot — Deal stage and next steps",
        "content": (
            "Deal: Acme Corp - Enterprise Platform\n"
            "Stage: Technical validation\n"
            "Amount: $420,000 ARR\n"
            "Champion: Amanda Chen (VP Engineering)\n"
            "Economic buyer: Robert Hayes (CTO)\n"
            "Next steps: Complete security questionnaire, schedule executive "
            "readout, confirm EU tenant timeline. Blocker: legal DPA review."
        ),
        "tags": ["hubspot", "crm", "acme", "deal"],
    },
]

POC_EPISODES = [
    {
        "name": "POC incident: load test OOM",
        "content": (
            "2026-05-10: Acme POC load test failed at 10k RPS with OOM. "
            "Root cause: per-request DB connections in POC branch. "
            "Mitigation: PR #89 merged; retest passed 2026-05-12."
        ),
    },
    {
        "name": "POC incident: SSO sandbox attribute mismatch",
        "content": (
            "2026-05-06: Acme IdP sent groups claim as multi-value; "
            "our sandbox expected single role string. Fixed mapping in "
            "config within 4 hours. No production impact."
        ),
    },
]

TIMELINE_EVENTS = [
    "2026-05-01: Discovery call — 500 seats, unified search across 12 SaaS tools.",
    "2026-05-06: POC kickoff — sandbox provisioned, GitHub repo acme-poc created.",
    "2026-05-10: Load test failure (OOM) — filed as poc-blocker.",
    "2026-05-12: Load test pass after connection pool fix.",
    "2026-05-15: Security questionnaire received; EU residency question open.",
    "2026-05-18: Executive readout scheduled; CTO wants graph search demo.",
]

DEAL_ENTITIES = [
    {
        "name": "Acme Corp",
        "entity_type": "organization",
        "properties": {"industry": "manufacturing", "deal_stage": "technical_validation"},
    },
    {
        "name": "SSO Production Commitment",
        "entity_type": "commitment",
        "properties": {"target_date": "2026-06-30", "status": "pending_legal"},
    },
    {
        "name": "POC Load Test Failure",
        "entity_type": "incident",
        "properties": {"severity": "blocker", "resolved": True},
    },
    {
        "name": "Amanda Chen",
        "entity_type": "person",
        "properties": {"title": "VP Engineering", "role": "champion"},
    },
]

HANDOFF_QUERIES = [
    "What broke during the Acme Corp POC load test and how was it fixed?",
    "What is our committed SSO timeline for Acme and what is still blocking production?",
    "Summarize open security and compliance items for the Acme deal.",
    "What should a backup SE know before the executive readout with Acme's CTO?",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}\n")


def extract_id(response, key: str = "id") -> str | None:
    data = response.json()
    return data.get(key) or data.get("id")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Main workflow
# ---------------------------------------------------------------------------

def create_org_and_project(client: MemDogClient) -> tuple[str, str]:
    """Create pre-sales org and Acme deal project."""
    section("1. Organization & Project Setup")

    org_id = ""
    print("  Creating organization: Pre-Sales Engineering...")
    try:
        resp = client.create_organization({
            "name": "Pre-Sales Engineering",
            "description": "Technical win room and enterprise POC knowledge",
        })
        resp.raise_for_status()
        data = resp.json()
        org_id = data.get("org_id") or data.get("id") or data.get("organization_id") or ""
        print(f"    Org ID: {org_id}")
    except Exception as exc:
        print(f"    (error: {exc})")

    project_id = ""
    if org_id:
        print(f"  Creating project: {DEAL_ID}...")
        try:
            resp = client.create_project(org_id, {
                "name": DEAL_NAME,
                "description": "Acme Corp enterprise deal — technical win room",
            })
            resp.raise_for_status()
            data = resp.json()
            project_id = data.get("project_id") or data.get("id") or ""
            print(f"    Project ID: {project_id}")
        except Exception as exc:
            print(f"    (error: {exc})")

    return org_id, project_id


def create_se_users(client: MemDogClient, org_id: str) -> list[str]:
    """Create sales engineer accounts and add them to the org."""
    section("2. Sales Engineer Accounts")
    user_ids: list[str] = []
    for se in SALES_ENGINEERS:
        print(f"  Creating user: {se['display_name']}...")
        try:
            resp = client.create_user({
                "username": se["username"],
                "display_name": se["display_name"],
                "email": se["email"],
            })
            resp.raise_for_status()
            data = resp.json()
            uid = data.get("user_id") or data.get("id") or ""
            user_ids.append(uid)
            print(f"    User ID: {uid}")

            if org_id and uid:
                try:
                    add_resp = client.add_org_member(org_id, uid, se["role"])
                    add_resp.raise_for_status()
                    print(f"    Added to org as {se['role']}")
                except Exception as exc:
                    print(f"    (failed to add to org: {exc})")
        except Exception as exc:
            print(f"    (error: {exc})")
            user_ids.append("")

    return user_ids


def create_deal_memories(client: MemDogClient, user_ids: list[str]) -> dict[str, str]:
    """Create typed memories for the Acme deal."""
    section("3. Deal Memories (Typed)")
    memory_map: dict[str, str] = {}
    valid_users = [u for u in user_ids if u]

    memory_specs = [
        {
            "key": "deal_org",
            "memory_type": "organizational",
            "name": f"Deal: {DEAL_NAME}",
            "description": "Deal-wide facts, architecture, and stakeholder map",
            "access_level": "restricted",
            "shared_with": valid_users,
        },
        {
            "key": "playbook",
            "memory_type": "factual",
            "name": "SE Technical Playbook",
            "description": "Reusable answers — SSO, residency, POC checklist",
            "access_level": "shared",
            "no_expiry": True,
        },
        {
            "key": "war_room",
            "memory_type": "conversation",
            "name": "Slack War Room: Acme",
            "description": "Active Slack threads (1h TTL in production)",
            "access_level": "restricted",
            "shared_with": valid_users,
        },
        {
            "key": "poc_episodic",
            "memory_type": "episodic",
            "name": "Acme POC Incidents",
            "description": "POC failures and resolutions",
            "access_level": "restricted",
            "shared_with": valid_users,
        },
        {
            "key": "handoff_timeline",
            "memory_type": "timeline",
            "name": f"Timeline: {DEAL_NAME}",
            "description": "Chronological deal narrative for SE handoff",
            "access_level": "restricted",
            "shared_with": valid_users,
        },
    ]

    for spec in memory_specs:
        payload = {
            "memory_type": spec["memory_type"],
            "name": spec["name"],
            "description": spec["description"],
            "access_level": spec["access_level"],
        }
        if spec.get("shared_with"):
            payload["shared_with"] = spec["shared_with"]
        if spec.get("no_expiry"):
            payload["no_expiry"] = True

        print(f"  Creating {spec['memory_type']} memory: {spec['name']}...")
        try:
            resp = client.create_memory(payload)
            resp.raise_for_status()
            data = resp.json()
            mid = data.get("memory_id") or data.get("id") or ""
            memory_map[spec["key"]] = mid
            print(f"    Memory ID: {mid}")
        except Exception as exc:
            print(f"    (error: {exc})")

    return memory_map


def ingest_playbook(client: MemDogClient, memory_map: dict[str, str]) -> list[str]:
    """Store SE playbook entries in factual memory."""
    section("4. SE Playbook (Factual Memory)")
    mid = memory_map.get("playbook")
    data_ids: list[str] = []
    for entry in SE_PLAYBOOK:
        try:
            resp = client.create_data(
                content=entry["content"],
                name=entry["name"],
                tags=entry["tags"],
                memory_ids=[mid] if mid else None,
            )
            resp.raise_for_status()
            did = extract_id(resp, "data_id") or ""
            data_ids.append(did)
            print(f"  [{did}] {entry['name']}")
        except Exception as exc:
            print(f"  (error: {exc})")
    return data_ids


def ingest_deal_artifacts(client: MemDogClient, memory_map: dict[str, str]) -> list[str]:
    """Ingest multi-channel deal artifacts."""
    section("5. Multi-Channel Deal Artifacts")
    deal_mid = memory_map.get("deal_org")
    war_mid = memory_map.get("war_room")
    data_ids: list[str] = []

    for artifact in DEAL_ARTIFACTS:
        mem_ids = []
        if deal_mid:
            mem_ids.append(deal_mid)
        if artifact["channel"] == "slack" and war_mid:
            mem_ids.append(war_mid)

        try:
            resp = client.create_data(
                content=artifact["content"],
                name=artifact["name"],
                tags=artifact["tags"] + [artifact["channel"], "acme-corp"],
                memory_ids=mem_ids or None,
            )
            resp.raise_for_status()
            did = extract_id(resp, "data_id") or ""
            data_ids.append(did)
            print(f"  [{artifact['channel']:<8}] {did} — {artifact['name'][:50]}")
        except Exception as exc:
            print(f"  (error for {artifact['name']}: {exc})")

    return data_ids


def ingest_poc_and_timeline(client: MemDogClient, memory_map: dict[str, str]) -> list[str]:
    """Record POC episodes and timeline events."""
    section("6. POC Episodes & Deal Timeline")
    episodic_mid = memory_map.get("poc_episodic")
    timeline_mid = memory_map.get("handoff_timeline")
    data_ids: list[str] = []

    for episode in POC_EPISODES:
        try:
            resp = client.create_data(
                content=episode["content"],
                name=episode["name"],
                tags=["poc", "episodic", "acme"],
                memory_ids=[episodic_mid] if episodic_mid else None,
            )
            resp.raise_for_status()
            did = extract_id(resp, "data_id") or ""
            data_ids.append(did)
            print(f"  [episodic] {episode['name']}")
        except Exception as exc:
            print(f"  (error: {exc})")

    for i, event in enumerate(TIMELINE_EVENTS, 1):
        try:
            resp = client.create_data(
                content=event,
                name=f"{DEAL_NAME} — Timeline #{i}",
                tags=["timeline", "acme", "handoff"],
                memory_ids=[timeline_mid] if timeline_mid else None,
            )
            resp.raise_for_status()
            did = extract_id(resp, "data_id") or ""
            data_ids.append(did)
        except Exception as exc:
            print(f"  (error on timeline #{i}: {exc})")

    print(f"\n  Timeline entries: {len(TIMELINE_EVENTS)}")
    return data_ids


def manage_deal_stage(client: MemDogClient) -> None:
    """Track deal stage in the key-value store."""
    section("7. Deal Stage (Key-Value Store)")
    deal_key = f"deal:{DEAL_ID}"

    initial = {
        "deal_id": DEAL_ID,
        "name": DEAL_NAME,
        "stage": "discovery",
        "owner": "Maya Rodriguez",
        "arr": 420000,
        "opened_at": "2026-05-01T00:00:00Z",
        "last_updated": now_iso(),
    }

    print(f"  Setting {deal_key}...")
    try:
        resp = client.set_store_value(deal_key, initial)
        resp.raise_for_status()
        print(f"    Stage: {initial['stage']}")
    except Exception as exc:
        print(f"    (error: {exc})")
        return

    for stage in ("poc", "security_review", "negotiation"):
        merged = {**initial, "stage": stage, "last_updated": now_iso()}
        try:
            resp = client.set_store_value(deal_key, merged)
            resp.raise_for_status()
            print(f"    Updated -> stage={stage}")
        except Exception as exc:
            print(f"    (error updating to {stage}: {exc})")

    print(f"\n  Reading final state for {deal_key}...")
    try:
        resp = client.get_store_value(deal_key)
        resp.raise_for_status()
        state = resp.json()
        print(f"    Stage: {state.get('stage', '?')}")
        print(f"    Owner: {state.get('owner', '?')}")
        print(f"    ARR:   ${state.get('arr', 0):,}")
    except Exception as exc:
        print(f"    (error: {exc})")

    print("\n  Listing deal keys (prefix deal:)...")
    try:
        resp = client.list_store_keys(prefix="deal:")
        resp.raise_for_status()
        keys = resp.json()
        items = keys if isinstance(keys, list) else keys.get("keys", keys.get("items", []))
        for k in items:
            name = k if isinstance(k, str) else k.get("key", k)
            print(f"    - {name}")
        if not items:
            print("    (no keys listed)")
    except Exception as exc:
        print(f"    (error: {exc})")


def create_deal_entities(client: MemDogClient) -> list[str]:
    """Create knowledge graph entities for the deal."""
    section("8. Deal Entities (Knowledge Graph)")
    try:
        resp = client.batch_create_entities({"entities": DEAL_ENTITIES})
        resp.raise_for_status()
        result = resp.json()
        entity_ids = result.get("entity_ids", [])
        for eid, ent in zip(entity_ids, DEAL_ENTITIES):
            print(f"  [{eid}] {ent['name']} ({ent['entity_type']})")
        return entity_ids
    except Exception as exc:
        print(f"  Batch create failed ({exc}), creating individually...")
        entity_ids: list[str] = []
        for ent in DEAL_ENTITIES:
            try:
                resp = client.batch_create_entities({"entities": [ent]})
                resp.raise_for_status()
                result = resp.json()
                eids = result.get("entity_ids", [])
                eid = eids[0] if eids else "?"
                entity_ids.append(eid)
                print(f"  [{eid}] {ent['name']} ({ent['entity_type']})")
            except Exception as inner_exc:
                print(f"  Failed: {ent['name']} — {inner_exc}")
        return entity_ids


def compare_search_modes(client: MemDogClient) -> None:
    """Compare search modes on a technical deal question."""
    section("9. Search Mode Comparison (Technical Query)")
    query = "Acme Corp SSO production commitment and blockers"

    print(f"  Query: \"{query}\"\n")
    print(f"  {'Mode':<10} {'Results':<8} Top result")
    print(f"  {'-' * 10} {'-' * 8} {'-' * 42}")

    for mode in SEARCH_MODES:
        try:
            resp = client.semantic_search(query, search_mode=mode, reranker="rrf", limit=3)
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", data.get("items", []))
            count = len(results)
            if results:
                top = results[0]
                top_name = (top.get("name") or top.get("data_id", "?"))[:42]
            else:
                top_name = "(none)"
            print(f"  {mode:<10} {count:<8} {top_name}")
        except Exception as exc:
            print(f"  {mode:<10} {'err':<8} {str(exc)[:42]}")


def run_handoff_briefing(client: MemDogClient) -> None:
    """RAG chat for SE handoff and executive prep."""
    section("10. SE Handoff Briefing (RAG Chat)")
    history: list[dict[str, str]] = []
    for query in HANDOFF_QUERIES:
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
                preview = answer[:320] + ("..." if len(answer) > 320 else "")
                print(f"  A: {preview}")
            else:
                print(f"  A: {answer}")

            history.append({"role": "user", "content": query})
            history.append({"role": "assistant", "content": str(answer)[:500]})
        except Exception as exc:
            print(f"  A: (error: {exc})")
        print()


def ai_deal_search(m: MemDog) -> None:
    """High-level AI search via MemDog facade."""
    section("11. AI-Powered Deal Search")
    queries = [
        "What environment was used for the Acme load test and what failed?",
        "Who is the champion at Acme and what do they care about?",
    ]
    for query in queries:
        print(f"  Q: {query}")
        try:
            results = m.search(query, use_ai=True)
            if results:
                answer = results[0]
                text = answer.get("response", answer.get("answer", str(answer)))
                if isinstance(text, str):
                    preview = text[:280] + ("..." if len(text) > 280 else "")
                    print(f"  A: {preview}")
                else:
                    print(f"  A: {text}")
            else:
                print("  A: (no results)")
        except Exception as exc:
            print(f"  A: (error: {exc})")
        print()


def cleanup_deal_kv(client: MemDogClient) -> None:
    """Remove demo KV key."""
    section("12. Cleanup")
    deal_key = f"deal:{DEAL_ID}"
    print(f"  Deleting store key {deal_key}...")
    try:
        resp = client.delete_store_value(deal_key)
        resp.raise_for_status()
        print("    Deleted.")
    except Exception as exc:
        print(f"    (error: {exc})")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Run the technical win room demo."""
    print("Technical Win Room -- mem-dog Example")
    print(f"API: {BASE_URL}")

    if not API_KEY:
        print("\nWARNING: MEM_DOG_API_KEY not set. Requests may fail.\n")

    m = MemDog(BASE_URL, api_key=API_KEY)
    client = m.client

    org_id, _project_id = create_org_and_project(client)
    user_ids = create_se_users(client, org_id)

    memory_map = create_deal_memories(client, user_ids)
    ingest_playbook(client, memory_map)
    ingest_deal_artifacts(client, memory_map)
    ingest_poc_and_timeline(client, memory_map)
    manage_deal_stage(client)
    create_deal_entities(client)

    print("\n  Waiting 2s for embedding generation...")
    time.sleep(2)

    compare_search_modes(client)
    run_handoff_briefing(client)
    ai_deal_search(m)
    cleanup_deal_kv(client)

    print("\nDone.")


if __name__ == "__main__":
    main()
