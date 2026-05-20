"""Sales CRM Knowledge Base -- mem-dog example.

Manage customer interactions with organization hierarchy, projects,
and access-controlled shared memories.

Usage:
    export MEM_DOG_URL=http://localhost:8080
    export MEM_DOG_API_KEY=your-key
    python main.py
"""

import os
import time

from mem_dog_client import MemDog, MemDogClient

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = os.environ.get("MEM_DOG_URL", "http://localhost:8080")
API_KEY = os.environ.get("MEM_DOG_API_KEY", "")

# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

# Sales reps
SALES_REPS = [
    {"username": "jmartinez", "display_name": "Jessica Martinez", "email": "jessica@acmesales.com"},
    {"username": "bthompson", "display_name": "Brian Thompson", "email": "brian@acmesales.com"},
]

# Deals / customer interactions
DEALS = [
    {
        "name": "Globex Corp - Enterprise License",
        "stage": "negotiation",
        "value": 280000,
        "contact": "Amanda Chen, VP Engineering",
        "notes": [
            (
                "Initial call with Amanda Chen (VP Eng) at Globex Corp. "
                "They need an enterprise license for 500+ seats. "
                "Current pain points: fragmented data across 12 SaaS tools, "
                "no unified search. Budget approved for Q3. "
                "Next step: technical demo on June 5."
            ),
            (
                "Technical demo went well. Their CTO (Robert Hayes) attended. "
                "Impressed by hybrid search and knowledge graph features. "
                "Concerns: data residency (need EU option), SSO integration. "
                "Action: send SOC 2 report and data residency whitepaper."
            ),
        ],
        "tags": ["enterprise", "negotiation", "globex"],
    },
    {
        "name": "Initech - Team Pilot",
        "stage": "discovery",
        "value": 45000,
        "contact": "Bill Lumbergh, Director of Operations",
        "notes": [
            (
                "Discovery call with Bill Lumbergh at Initech. "
                "Small team (30 users) looking for knowledge management. "
                "Main use case: internal wiki replacement with AI search. "
                "Currently using Confluence, unhappy with search quality. "
                "Budget: $50K annual, needs approval from CFO."
            ),
        ],
        "tags": ["pilot", "discovery", "initech", "smb"],
    },
    {
        "name": "Stark Industries - Platform Integration",
        "stage": "closed-won",
        "value": 520000,
        "contact": "Pepper Potts, COO",
        "notes": [
            (
                "Contract signed! Stark Industries -- 2-year platform deal. "
                "1,200 seats, full API access, dedicated support tier. "
                "Key differentiator was our webhook pipeline and 42-agent "
                "enrichment system. Integration with their Jarvis platform "
                "starts July 1. Champion: Tony (CEO) personally approved."
            ),
            (
                "Onboarding kickoff with Pepper Potts and tech lead Happy Hogan. "
                "Phase 1: Slack + Gmail integration (July). "
                "Phase 2: Custom webhook for Jarvis data (August). "
                "Phase 3: Knowledge graph for R&D docs (September). "
                "Dedicated CSM assigned: Jessica Martinez."
            ),
        ],
        "tags": ["enterprise", "closed-won", "stark", "integration"],
    },
]

# Competitive intelligence
COMPETITIVE_INTEL = [
    {
        "competitor": "Notion AI",
        "content": (
            "Notion AI Competitive Brief (May 2026)\n\n"
            "Strengths: Strong brand, large user base, good UX for docs.\n"
            "Weaknesses: No knowledge graph, limited search modes (vector only), "
            "no webhook pipeline, no multi-channel ingestion.\n"
            "Our advantage: 5 search modes, 42-agent enrichment, "
            "temporal knowledge graph, enterprise access controls.\n"
            "Positioning: We win on search quality and AI depth."
        ),
    },
    {
        "competitor": "Mem.ai",
        "content": (
            "Mem.ai Competitive Brief (May 2026)\n\n"
            "Strengths: Good personal knowledge management, clean UI.\n"
            "Weaknesses: No org features, no access controls, "
            "single-user focus, no on-prem/self-hosted option.\n"
            "Our advantage: Full org hierarchy, project scoping, "
            "access levels (private/shared/public/restricted), "
            "self-hosted option.\n"
            "Positioning: We win on enterprise and team features."
        ),
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}\n")


def extract_id(response, key="id"):
    data = response.json()
    return data.get(key) or data.get(f"{key.split('_')[0]}_id") or data.get("id")


# ---------------------------------------------------------------------------
# Main workflow
# ---------------------------------------------------------------------------

def create_org_and_project(client: MemDogClient) -> tuple[str, str]:
    """Create the sales organization and a pipeline project."""
    section("1. Organization & Project Setup")

    # Create organization
    print("  Creating organization: Acme Sales Team...")
    org_id = None
    try:
        resp = client.create_organization({
            "name": "Acme Sales Team",
            "description": "Sales team knowledge base and CRM data",
        })
        resp.raise_for_status()
        data = resp.json()
        org_id = data.get("org_id") or data.get("id") or data.get("organization_id")
        print(f"    Org ID: {org_id}")
    except Exception as exc:
        print(f"    (error: {exc})")

    # Create project under org
    project_id = None
    if org_id:
        print("  Creating project: Q3 Pipeline...")
        try:
            resp = client.create_project(org_id, {
                "name": "Q3 Pipeline",
                "description": "Q3 2026 sales pipeline tracking",
            })
            resp.raise_for_status()
            data = resp.json()
            project_id = data.get("project_id") or data.get("id")
            print(f"    Project ID: {project_id}")
        except Exception as exc:
            print(f"    (error: {exc})")

    return org_id or "", project_id or ""


def create_sales_users(client: MemDogClient, org_id: str) -> list[str]:
    """Create user accounts for sales reps and add them to the org."""
    section("2. Sales Rep User Accounts")
    user_ids = []
    for rep in SALES_REPS:
        print(f"  Creating user: {rep['display_name']}...")
        try:
            resp = client.create_user({
                "username": rep["username"],
                "display_name": rep["display_name"],
                "email": rep["email"],
            })
            resp.raise_for_status()
            data = resp.json()
            uid = data.get("user_id") or data.get("id")
            user_ids.append(uid)
            print(f"    User ID: {uid}")

            # Add to organization
            if org_id and uid:
                role = "admin" if rep["username"] == "jmartinez" else "member"
                try:
                    add_resp = client.add_org_member(org_id, uid, role)
                    add_resp.raise_for_status()
                    print(f"    Added to org as {role}")
                except Exception as exc:
                    print(f"    (failed to add to org: {exc})")
        except Exception as exc:
            print(f"    (error: {exc})")
            user_ids.append("")

    return user_ids


def create_shared_memories(client: MemDogClient, user_ids: list[str]) -> dict[str, str]:
    """Create memories with different access levels."""
    section("3. Creating Shared Memories")
    memory_map = {}

    # Organizational memory -- visible to all org members
    print("  Creating org-level competitive intel memory (access=shared)...")
    try:
        resp = client.create_memory({
            "memory_type": "organizational",
            "name": "Competitive Intelligence",
            "description": "Competitor analysis and positioning notes",
            "access_level": "shared",
        })
        resp.raise_for_status()
        data = resp.json()
        mid = data.get("memory_id") or data.get("id")
        memory_map["competitive_intel"] = mid
        print(f"    Memory ID: {mid}")
    except Exception as exc:
        print(f"    (error: {exc})")

    # Restricted deal notes -- only shared with specific reps
    for deal in DEALS:
        deal_key = deal["name"].split(" - ")[0].lower().replace(" ", "_")
        valid_user_ids = [uid for uid in user_ids if uid]
        print(f"  Creating deal memory: {deal['name']} (access=restricted)...")
        try:
            resp = client.create_memory({
                "memory_type": "conversation",
                "name": f"Deal Notes: {deal['name']}",
                "description": f"Stage: {deal['stage']}, Value: ${deal['value']:,}",
                "access_level": "restricted",
                "shared_with": valid_user_ids[:2],  # both reps can see
            })
            resp.raise_for_status()
            data = resp.json()
            mid = data.get("memory_id") or data.get("id")
            memory_map[deal_key] = mid
            print(f"    Memory ID: {mid}")
        except Exception as exc:
            print(f"    (error: {exc})")

    return memory_map


def ingest_deal_notes(client: MemDogClient, memory_map: dict[str, str]) -> list[str]:
    """Store deal interaction notes attached to their memories."""
    section("4. Ingesting Deal Notes")
    data_ids = []
    for deal in DEALS:
        deal_key = deal["name"].split(" - ")[0].lower().replace(" ", "_")
        mid = memory_map.get(deal_key)
        for i, note in enumerate(deal["notes"], 1):
            try:
                resp = client.create_data(
                    content=note,
                    name=f"{deal['name']} - Note #{i}",
                    tags=deal["tags"],
                    memory_ids=[mid] if mid else None,
                )
                resp.raise_for_status()
                data = resp.json()
                did = data.get("data_id") or data.get("id")
                data_ids.append(did)
                print(f"  [{did}] {deal['name']} - Note #{i}")
                if mid:
                    print(f"           attached to memory {mid}")
            except Exception as exc:
                print(f"  (error storing note for {deal['name']}: {exc})")
    return data_ids


def ingest_competitive_intel(client: MemDogClient, memory_map: dict[str, str]) -> list[str]:
    """Store competitive intelligence in the shared org memory."""
    section("5. Ingesting Competitive Intelligence")
    mid = memory_map.get("competitive_intel")
    data_ids = []
    for intel in COMPETITIVE_INTEL:
        try:
            resp = client.create_data(
                content=intel["content"],
                name=f"Competitive Brief: {intel['competitor']}",
                tags=["competitive-intel", intel["competitor"].lower().replace(" ", "-")],
                memory_ids=[mid] if mid else None,
            )
            resp.raise_for_status()
            data = resp.json()
            did = data.get("data_id") or data.get("id")
            data_ids.append(did)
            print(f"  [{did}] {intel['competitor']}")
        except Exception as exc:
            print(f"  (error: {exc})")
    return data_ids


def demo_access_controls(client: MemDogClient, data_ids: list[str], user_ids: list[str]) -> None:
    """Demonstrate access control checks and updates."""
    section("6. Access Control Demo")
    if not data_ids:
        print("  No data to check access on.")
        return

    test_id = data_ids[0]
    print(f"  Checking access on {test_id}...")

    # Read current access
    try:
        resp = client.get_access(test_id)
        resp.raise_for_status()
        access = resp.json()
        print(f"    Current access: {access}")
    except Exception as exc:
        print(f"    (error reading access: {exc})")

    # Update access to shared
    print(f"\n  Updating access to 'shared'...")
    try:
        resp = client.update_access(test_id, user_ids[:2] if user_ids else None)
        resp.raise_for_status()
        print("    Access updated.")
    except Exception as exc:
        print(f"    (error: {exc})")

    # Check if a specific user has access
    if user_ids and user_ids[0]:
        print(f"\n  Checking if {SALES_REPS[0]['display_name']} has access...")
        try:
            resp = client.check_access(test_id, user_id=user_ids[0])
            resp.raise_for_status()
            result = resp.json()
            has_access = result.get("has_access", result.get("allowed", "?"))
            print(f"    Has access: {has_access}")
        except Exception as exc:
            print(f"    (error: {exc})")


def search_deal_briefing(m: MemDog) -> None:
    """Use AI search to generate deal briefings."""
    section("7. AI-Powered Deal Briefings")
    queries = [
        "What is the status of the Globex Corp deal and what are their concerns?",
        "Which deals have closed and what were the key differentiators?",
        "What are our competitive advantages over Notion AI?",
        "Summarize all active deals and their next steps",
    ]
    for query in queries:
        print(f"  Q: {query}")
        try:
            results = m.search(query, use_ai=True)
            if results:
                answer = results[0]
                text = answer.get("response", answer.get("answer", str(answer)))
                if isinstance(text, str):
                    preview = text[:300] + ("..." if len(text) > 300 else "")
                    print(f"  A: {preview}")
                else:
                    print(f"  A: {text}")
            else:
                print("  A: (no results)")
        except Exception as exc:
            print(f"  A: (error: {exc})")
        print()


def list_org_structure(client: MemDogClient, org_id: str) -> None:
    """Display the organization structure."""
    section("8. Organization Structure")
    if not org_id:
        print("  No org created.")
        return

    # List org details
    try:
        resp = client.get_organization(org_id)
        resp.raise_for_status()
        org = resp.json()
        print(f"  Org: {org.get('name', '?')}")
        print(f"  Description: {org.get('description', 'N/A')}")
    except Exception as exc:
        print(f"  (error: {exc})")

    # List members
    print("\n  Members:")
    try:
        resp = client.list_org_members(org_id)
        resp.raise_for_status()
        members = resp.json()
        items = members if isinstance(members, list) else members.get("members", members.get("items", []))
        for m in items:
            uid = m.get("user_id", "?")
            role = m.get("role", "?")
            name = m.get("display_name", m.get("username", uid))
            print(f"    - {name} ({role})")
        if not items:
            print("    (no members listed)")
    except Exception as exc:
        print(f"    (error: {exc})")

    # List projects
    print("\n  Projects:")
    try:
        resp = client.list_projects(org_id)
        resp.raise_for_status()
        projects = resp.json()
        items = projects if isinstance(projects, list) else projects.get("projects", projects.get("items", []))
        for p in items:
            pid = p.get("project_id", p.get("id", "?"))
            name = p.get("name", "?")
            print(f"    - [{pid}] {name}")
        if not items:
            print("    (no projects listed)")
    except Exception as exc:
        print(f"    (error: {exc})")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Run the sales CRM knowledge base demo."""
    print("Sales CRM Knowledge Base -- mem-dog Example")
    print(f"API: {BASE_URL}")

    if not API_KEY:
        print("\nWARNING: MEM_DOG_API_KEY not set. Requests may fail.\n")

    client = MemDogClient(base_url=BASE_URL, api_key=API_KEY)
    m = MemDog(BASE_URL, api_key=API_KEY)

    # Build org structure
    org_id, project_id = create_org_and_project(client)
    user_ids = create_sales_users(client, org_id)

    # Create shared memories with access controls
    memory_map = create_shared_memories(client, user_ids)

    # Ingest data
    deal_data_ids = ingest_deal_notes(client, memory_map)
    intel_data_ids = ingest_competitive_intel(client, memory_map)

    # Wait for embeddings
    print("\n  Waiting 2s for embedding generation...")
    time.sleep(2)

    # Access controls
    demo_access_controls(client, deal_data_ids, user_ids)

    # AI-powered search
    search_deal_briefing(m)

    # Display org structure
    list_org_structure(client, org_id)

    print("\nDone.")


if __name__ == "__main__":
    main()
