"""Financial Compliance Monitor -- mem-dog example.

Track regulations with temporal awareness. Query point-in-time facts,
manage document versions, and build compliance dashboards.

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
# Sample data: 6 regulatory items across different effective dates
# ---------------------------------------------------------------------------

REGULATIONS = [
    {
        "title": "AML Reporting Threshold - Domestic",
        "content": "Anti-Money Laundering: Financial institutions must file a Currency "
                   "Transaction Report (CTR) for transactions exceeding $10,000. Multiple "
                   "transactions by the same customer aggregating over $10,000 in a single "
                   "business day also trigger reporting requirements.",
        "effective_date": "2024-01-01",
        "category": "aml",
        "jurisdiction": "US",
    },
    {
        "title": "AML Reporting Threshold - International",
        "content": "Cross-border wire transfers exceeding $3,000 require enhanced due "
                   "diligence and must include originator and beneficiary information per "
                   "the Travel Rule (31 CFR 1010.410).",
        "effective_date": "2024-01-01",
        "category": "aml",
        "jurisdiction": "US",
    },
    {
        "title": "GDPR Data Retention - Financial Records",
        "content": "Under GDPR Article 5(1)(e), personal data in financial records may "
                   "be retained for the period required by local tax/AML legislation "
                   "(typically 5-7 years), after which it must be anonymized or deleted.",
        "effective_date": "2024-03-15",
        "category": "data_privacy",
        "jurisdiction": "EU",
    },
    {
        "title": "Basel III Capital Adequacy Ratio",
        "content": "Banks must maintain a minimum Common Equity Tier 1 (CET1) ratio of "
                   "4.5%, a Tier 1 capital ratio of 6%, and a total capital ratio of 8%. "
                   "G-SIBs carry an additional surcharge of 1-3.5%.",
        "effective_date": "2024-06-01",
        "category": "capital_requirements",
        "jurisdiction": "GLOBAL",
    },
    {
        "title": "SOX Section 404 - Internal Controls",
        "content": "Public companies must document and test internal controls over "
                   "financial reporting annually. Management must assess effectiveness "
                   "and external auditors must attest to the assessment.",
        "effective_date": "2025-01-01",
        "category": "reporting",
        "jurisdiction": "US",
    },
    {
        "title": "MiCA Crypto Asset Regulation",
        "content": "Markets in Crypto-Assets Regulation requires crypto-asset service "
                   "providers (CASPs) to obtain authorization, maintain capital reserves, "
                   "and implement customer complaint handling procedures within the EU.",
        "effective_date": "2025-06-30",
        "category": "crypto",
        "jurisdiction": "EU",
    },
]

# 2 policy versions: original and updated
POLICY_VERSIONS = {
    "title": "Internal Trading Compliance Policy",
    "v1": (
        "Version 1.0 (2024-01-15): Employees must pre-clear all trades in company "
        "securities with the Compliance Office. Blackout periods apply 14 days before "
        "earnings releases. Maximum holding period exemption: trades under $5,000."
    ),
    "v2": (
        "Version 2.0 (2025-03-01): Employees must pre-clear all trades in company "
        "securities AND related derivatives with the Compliance Office. Blackout periods "
        "extended to 21 days before earnings releases. Maximum holding period exemption "
        "removed -- all trades require pre-clearance regardless of size. New: mandatory "
        "annual certification of compliance with trading policy."
    ),
}


def ingest_regulatory_documents(client: MemDogClient) -> list[str]:
    """Store regulatory documents with organizational memories."""
    print("=" * 60)
    print("STEP 1: Ingesting Regulatory Documents")
    print("=" * 60)

    data_ids = []
    for reg in REGULATIONS:
        # Create the data item
        resp = client.create_data(
            content=reg["content"],
            name=reg["title"],
            tags=[reg["category"], reg["jurisdiction"].lower(), "regulation",
                  f"effective:{reg['effective_date']}"],
        )
        resp.raise_for_status()
        data = resp.json()
        data_id = data.get("data_id") or data.get("id")
        data_ids.append(data_id)
        print(f"  [{reg['jurisdiction']:6}] {reg['title'][:45]}...")
        print(f"           data_id={data_id}  effective={reg['effective_date']}")

    # Create a permanent organizational memory to group them
    mem_resp = client.create_memory({
        "memory_type": "organizational",
        "name": "Regulatory Compliance Library",
        "description": "All active regulatory documents and requirements",
        "no_expiry": True,
        "access_level": "shared",
    })
    mem_resp.raise_for_status()
    mem_data = mem_resp.json()
    memory_id = mem_data.get("memory_id") or mem_data.get("id")
    print(f"\n  Organizational memory: {memory_id} (no_expiry=True)")

    # Attach all documents to the memory
    attach_resp = client.add_data_to_memory(memory_id, data_ids)
    attach_resp.raise_for_status()
    print(f"  Attached {len(data_ids)} documents to memory")

    return data_ids


def demonstrate_versioning(client: MemDogClient) -> str:
    """Create a policy document and update it to show versioning."""
    print("\n" + "=" * 60)
    print("STEP 2: Document Versioning")
    print("=" * 60)

    # Create the original version
    resp = client.create_data(
        content=POLICY_VERSIONS["v1"],
        name=POLICY_VERSIONS["title"],
        tags=["policy", "trading", "internal"],
    )
    resp.raise_for_status()
    data = resp.json()
    data_id = data.get("data_id") or data.get("id")
    print(f"  Created policy: {POLICY_VERSIONS['title']}")
    print(f"  data_id={data_id}")
    print(f"  Version 1: {POLICY_VERSIONS['v1'][:60]}...")

    # Update to version 2
    update_resp = client.update_data(data_id, content=POLICY_VERSIONS["v2"])
    update_resp.raise_for_status()
    print(f"\n  Updated to Version 2: {POLICY_VERSIONS['v2'][:60]}...")

    # List all versions
    versions_resp = client.list_versions(data_id)
    versions_resp.raise_for_status()
    versions = versions_resp.json()
    version_list = versions if isinstance(versions, list) else versions.get("versions", [])
    print(f"\n  Version history ({len(version_list)} versions):")
    for v in version_list:
        ver_num = v.get("version", "?")
        created = v.get("created_at", "unknown")
        print(f"    v{ver_num} - created: {created}")

    # Retrieve specific version (v1)
    if version_list:
        v1_resp = client.get_version(data_id, 1)
        v1_resp.raise_for_status()
        ct = v1_resp.headers.get("content-type", "")
        if "json" in ct:
            v1_content = v1_resp.json()
        else:
            v1_content = v1_resp.text
        print(f"\n  Retrieved v1 content: {str(v1_content)[:60]}...")

    return data_id


def query_temporal_facts(client: MemDogClient) -> None:
    """Query point-in-time facts using the knowledge graph."""
    print("\n" + "=" * 60)
    print("STEP 3: Temporal Fact Queries (Knowledge Graph)")
    print("=" * 60)

    # Query facts about reporting thresholds at a specific point in time
    print("\n  -- Query: 'reporting threshold' as of 2025-06-01 --")
    resp = client.query_facts(q="reporting threshold", at="2025-06-01T00:00:00Z")
    resp.raise_for_status()
    facts = resp.json()
    fact_list = facts if isinstance(facts, list) else facts.get("facts", [])
    print(f"  Found {len(fact_list)} temporal facts:")
    for f in fact_list[:5]:
        subject = f.get("subject", f.get("entity_name", "?"))
        fact_text = f.get("fact", f.get("content", "?"))
        valid_at = f.get("valid_at", "?")
        print(f"    - [{valid_at}] {subject}: {str(fact_text)[:50]}...")

    # Query facts about capital requirements
    print("\n  -- Query: 'capital adequacy ratio' as of 2024-07-01 --")
    resp2 = client.query_facts(q="capital adequacy ratio", at="2024-07-01T00:00:00Z")
    resp2.raise_for_status()
    facts2 = resp2.json()
    fact_list2 = facts2 if isinstance(facts2, list) else facts2.get("facts", [])
    print(f"  Found {len(fact_list2)} temporal facts")

    # Get fact timeline for an entity
    print("\n  -- Fact timeline for AML regulations --")
    # Search for AML entity first
    entities_resp = client.search_entities("AML", entity_type="regulation")
    entities_resp.raise_for_status()
    entities = entities_resp.json()
    entity_list = entities if isinstance(entities, list) else []
    if entity_list:
        entity_id = entity_list[0].get("entity_id") or entity_list[0].get("id")
        tl_resp = client.get_fact_timeline(entity_id)
        tl_resp.raise_for_status()
        timeline = tl_resp.json()
        events = timeline if isinstance(timeline, list) else timeline.get("timeline", [])
        print(f"  Entity: {entity_list[0].get('name', entity_id)}")
        print(f"  Timeline entries: {len(events)}")
        for evt in events[:3]:
            print(f"    {evt.get('valid_at', '?')}: {str(evt.get('fact', ''))[:50]}...")
    else:
        print("  No AML entities found in graph (graph may not be enabled)")


def semantic_search_regulations(client: MemDogClient) -> None:
    """Search regulations using graph mode and temporal filters."""
    print("\n" + "=" * 60)
    print("STEP 4: Semantic Search with Graph Mode")
    print("=" * 60)

    # Graph-mode search with temporal filter
    print("\n  -- Graph search: 'crypto regulation' (temporal: 2025-01-01) --")
    resp = client.semantic_search(
        "crypto asset regulation requirements",
        search_mode="graph",
        temporal_filter="2025-01-01",
        limit=5,
    )
    resp.raise_for_status()
    results = resp.json()
    items = results.get("results", results.get("items", []))
    if isinstance(results, list):
        items = results
    print(f"  Results: {len(items)}")
    for r in items[:3]:
        name = r.get("name", r.get("title", "untitled"))
        score = r.get("score", r.get("relevance", "n/a"))
        print(f"    - {name} (score={score})")

    # Hybrid search for cross-border compliance
    print("\n  -- Hybrid search: 'cross-border wire transfer requirements' --")
    resp2 = client.semantic_search(
        "cross-border wire transfer requirements",
        search_mode="hybrid",
        reranker="cross-encoder",
        limit=5,
    )
    resp2.raise_for_status()
    results2 = resp2.json()
    items2 = results2.get("results", results2.get("items", []))
    if isinstance(results2, list):
        items2 = results2
    print(f"  Results: {len(items2)}")
    for r in items2[:3]:
        name = r.get("name", r.get("title", "untitled"))
        score = r.get("score", r.get("relevance", "n/a"))
        print(f"    - {name} (score={score})")


def build_compliance_dashboard(client: MemDogClient) -> None:
    """Pull platform and data stats for a compliance dashboard."""
    print("\n" + "=" * 60)
    print("STEP 5: Compliance Dashboard (Stats)")
    print("=" * 60)

    # Platform-wide stats
    print("\n  -- Platform Stats --")
    stats_resp = client.get_stats()
    stats_resp.raise_for_status()
    stats = stats_resp.json()
    for key in ["total_data", "total_memories", "total_users", "total_embeddings"]:
        if key in stats:
            print(f"    {key}: {stats[key]}")

    # Data-specific stats
    print("\n  -- Data Stats --")
    data_stats_resp = client.get_data_stats()
    data_stats_resp.raise_for_status()
    data_stats = data_stats_resp.json()
    for key in ["total_items", "total_size_bytes", "by_content_type"]:
        if key in data_stats:
            val = data_stats[key]
            if isinstance(val, dict):
                print(f"    {key}:")
                for k, v in list(val.items())[:5]:
                    print(f"      {k}: {v}")
            else:
                print(f"    {key}: {val}")

    # Memory-specific stats
    print("\n  -- Memory Stats --")
    mem_stats_resp = client.get_memory_stats()
    mem_stats_resp.raise_for_status()
    mem_stats = mem_stats_resp.json()
    for key in ["total_memories", "by_type", "by_access_level", "expired_count"]:
        if key in mem_stats:
            val = mem_stats[key]
            if isinstance(val, dict):
                print(f"    {key}:")
                for k, v in list(val.items())[:5]:
                    print(f"      {k}: {v}")
            else:
                print(f"    {key}: {val}")


def main():
    """Run the financial compliance monitor demo."""
    print("Financial Compliance Monitor -- mem-dog Example")
    print(f"API: {BASE_URL}")
    print(f"Time: {datetime.now().isoformat()}")
    print()

    client = MemDogClient(BASE_URL, api_key=API_KEY)

    # Step 1: Ingest regulatory documents
    data_ids = ingest_regulatory_documents(client)

    # Step 2: Demonstrate versioning
    policy_id = demonstrate_versioning(client)

    # Step 3: Temporal fact queries
    query_temporal_facts(client)

    # Step 4: Semantic search with graph mode
    semantic_search_regulations(client)

    # Step 5: Compliance dashboard
    build_compliance_dashboard(client)

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Regulatory documents:  {len(data_ids)}")
    print(f"  Policy (versioned):    {policy_id}")
    print(f"  Jurisdictions covered: US, EU, GLOBAL")
    print(f"  Categories:            aml, data_privacy, capital_requirements, reporting, crypto")
    print("\nDone.")


if __name__ == "__main__":
    main()
