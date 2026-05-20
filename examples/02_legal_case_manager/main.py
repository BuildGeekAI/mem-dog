"""Legal Case Manager -- mem-dog example.

Store case documents and legal precedents. Compare all 5 search modes
and 4 rerankers side-by-side. Track entity relationships.

Usage:
    export MEM_DOG_URL=http://localhost:8080
    export MEM_DOG_API_KEY=your-key
    python main.py
"""

import os
import sys
import time

from mem_dog_client import MemDogClient

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = os.environ.get("MEM_DOG_URL", "http://localhost:8080")
API_KEY = os.environ.get("MEM_DOG_API_KEY", "")

# Search modes and rerankers supported by mem-dog
SEARCH_MODES = ["vector", "fts", "hybrid", "graph", "full"]
RERANKERS = ["none", "rrf", "mmr", "cross-encoder"]

# ---------------------------------------------------------------------------
# Sample data -- case documents, precedents, entities
# ---------------------------------------------------------------------------

CASE_DOCUMENTS = [
    {
        "name": "Complaint - Rivera v. TechCorp Inc.",
        "tags": ["complaint", "employment", "discrimination"],
        "content": (
            "COMPLAINT FOR DAMAGES\n"
            "Case No. 2026-CV-04821\n\n"
            "Plaintiff Maria Rivera alleges that defendant TechCorp Inc. "
            "engaged in discriminatory employment practices in violation of "
            "Title VII of the Civil Rights Act. Plaintiff was employed as a "
            "Senior Software Engineer from January 2022 to March 2026. "
            "Despite consistently exceeding performance metrics, Plaintiff "
            "was passed over for promotion three times in favor of less "
            "qualified male colleagues. Plaintiff reported the pattern to HR "
            "on November 15, 2025, and was terminated two weeks later on "
            "November 29, 2025, in what constitutes unlawful retaliation."
        ),
    },
    {
        "name": "Deposition - James Chen (HR Director)",
        "tags": ["deposition", "witness", "hr"],
        "content": (
            "DEPOSITION OF JAMES CHEN, HR DIRECTOR, TECHCORP INC.\n"
            "Date: April 3, 2026\n\n"
            "Q: Mr. Chen, were you aware of Ms. Rivera's complaint?\n"
            "A: I received her written complaint on November 15, 2025.\n"
            "Q: What action did you take?\n"
            "A: I forwarded it to our legal department for review.\n"
            "Q: Was Ms. Rivera's termination related to her complaint?\n"
            "A: No. The termination was part of a planned restructuring.\n"
            "Q: How many employees were terminated in this restructuring?\n"
            "A: Three employees in the engineering department.\n"
            "Q: Were the other two employees also in protected classes?\n"
            "A: I would need to check our records on that."
        ),
    },
    {
        "name": "Performance Review - Maria Rivera (2025 Annual)",
        "tags": ["evidence", "performance", "plaintiff"],
        "content": (
            "ANNUAL PERFORMANCE REVIEW -- 2025\n"
            "Employee: Maria Rivera, Senior Software Engineer\n"
            "Reviewer: David Liu, Engineering Manager\n\n"
            "Overall Rating: Exceeds Expectations (4.5/5.0)\n"
            "Technical Skills: 5/5 -- Consistently delivers high-quality code.\n"
            "Leadership: 4/5 -- Mentors junior engineers effectively.\n"
            "Communication: 4/5 -- Clear and professional.\n"
            "Initiative: 5/5 -- Led the migration to microservices architecture.\n\n"
            "Reviewer Comments: Maria is one of our strongest engineers. "
            "She would be an excellent candidate for the Principal Engineer role."
        ),
    },
    {
        "name": "Internal Email - Restructuring Plan",
        "tags": ["evidence", "email", "restructuring"],
        "content": (
            "From: Sarah Walsh, VP Engineering\n"
            "To: James Chen, HR Director\n"
            "Date: November 20, 2025\n"
            "Subject: Q4 Restructuring Targets\n\n"
            "James, per our discussion, we need to reduce headcount in "
            "engineering by 3 positions. I've identified the following roles "
            "for elimination: 1) Senior QA Engineer (vacant), "
            "2) Junior DevOps Engineer, 3) Senior Software Engineer -- "
            "please process Maria Rivera's termination with the standard "
            "severance package. Timing is important -- we need this done "
            "before the holiday freeze. -- Sarah"
        ),
    },
    {
        "name": "Expert Witness Report - Dr. Patricia Gomez",
        "tags": ["expert-witness", "statistics", "discrimination"],
        "content": (
            "EXPERT STATISTICAL ANALYSIS\n"
            "Prepared by: Dr. Patricia Gomez, Ph.D. Industrial Psychology\n\n"
            "Analysis of promotion decisions at TechCorp Inc. (2020-2026) "
            "reveals a statistically significant gender disparity. "
            "Female engineers received promotions at a rate of 12% vs. 34% "
            "for male engineers with comparable qualifications (p < 0.001). "
            "The restructuring list of November 2025 disproportionately "
            "targeted employees who had filed internal complaints (2 of 3, "
            "vs. 0.5% base rate of complainants in the workforce). "
            "These patterns are consistent with systemic discrimination "
            "and retaliatory conduct."
        ),
    },
]

PRECEDENTS = [
    {
        "memory_type": "factual",
        "name": "McDonnell Douglas v. Green (1973)",
        "content": (
            "McDonnell Douglas Corp. v. Green, 411 U.S. 792 (1973). "
            "Established the burden-shifting framework for Title VII cases. "
            "Plaintiff must show: (1) membership in protected class, "
            "(2) qualification for the position, (3) adverse action, "
            "(4) circumstances suggesting discrimination. Burden then shifts "
            "to employer to articulate a legitimate, non-discriminatory reason."
        ),
    },
    {
        "memory_type": "factual",
        "name": "Burlington Northern v. White (2006)",
        "content": (
            "Burlington Northern & Santa Fe Railway Co. v. White, "
            "548 U.S. 53 (2006). Broadened the scope of anti-retaliation "
            "protections under Title VII. Any employer action that would "
            "dissuade a reasonable worker from making a charge of "
            "discrimination qualifies as unlawful retaliation, not limited "
            "to workplace or employment actions."
        ),
    },
    {
        "memory_type": "factual",
        "name": "Staub v. Proctor Hospital (2011)",
        "content": (
            "Staub v. Proctor Hospital, 562 U.S. 411 (2011). "
            "Established 'cat's paw' liability -- if a supervisor's "
            "discriminatory animus is the proximate cause of an adverse "
            "employment action, the employer is liable even if the final "
            "decision-maker had no discriminatory intent."
        ),
    },
]

CASE_TIMELINE = [
    {
        "memory_type": "episodic",
        "name": "Rivera hired at TechCorp",
        "content": "January 2022: Maria Rivera joins TechCorp Inc. as Senior Software Engineer.",
    },
    {
        "memory_type": "episodic",
        "name": "First promotion denial",
        "content": "June 2023: Rivera denied promotion to Principal Engineer. Position given to Mark Thompson (2 years less experience).",
    },
    {
        "memory_type": "episodic",
        "name": "HR complaint filed",
        "content": "November 15, 2025: Rivera files written discrimination complaint with HR Director James Chen.",
    },
    {
        "memory_type": "episodic",
        "name": "Rivera terminated",
        "content": "November 29, 2025: Rivera terminated as part of 'restructuring'. Two weeks after complaint.",
    },
]

# Entities to create manually
CASE_ENTITIES = [
    {"name": "Maria Rivera", "entity_type": "person", "properties": {"role": "plaintiff", "title": "Senior Software Engineer"}},
    {"name": "TechCorp Inc.", "entity_type": "organization", "properties": {"role": "defendant", "industry": "technology"}},
    {"name": "James Chen", "entity_type": "person", "properties": {"role": "witness", "title": "HR Director"}},
    {"name": "Judge Katherine Walsh", "entity_type": "person", "properties": {"role": "judge", "court": "US District Court"}},
    {"name": "Dr. Patricia Gomez", "entity_type": "person", "properties": {"role": "expert-witness", "specialty": "Industrial Psychology"}},
    {"name": "David Liu", "entity_type": "person", "properties": {"role": "witness", "title": "Engineering Manager"}},
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}\n")


def extract_id(response, key="data_id"):
    """Extract an ID from an httpx.Response JSON body."""
    data = response.json()
    return data.get(key) or data.get("id")


# ---------------------------------------------------------------------------
# Main workflow
# ---------------------------------------------------------------------------

def ingest_documents(client: MemDogClient) -> list[str]:
    """Store case documents with tags."""
    section("1. Ingesting Case Documents")
    data_ids = []
    for doc in CASE_DOCUMENTS:
        resp = client.create_data(
            content=doc["content"],
            name=doc["name"],
            tags=doc["tags"],
        )
        resp.raise_for_status()
        did = extract_id(resp)
        data_ids.append(did)
        print(f"  [{did}] {doc['name']}")
        print(f"           tags: {doc['tags']}")
    return data_ids


def create_precedents(client: MemDogClient) -> list[str]:
    """Create factual memories for legal precedents."""
    section("2. Creating Legal Precedents (Factual Memories)")
    memory_ids = []
    for prec in PRECEDENTS:
        # Create memory
        mem_resp = client.create_memory({
            "memory_type": prec["memory_type"],
            "name": prec["name"],
        })
        mem_resp.raise_for_status()
        mid = extract_id(mem_resp, "memory_id")
        memory_ids.append(mid)

        # Store content as data and attach to memory
        data_resp = client.create_data(
            content=prec["content"],
            name=prec["name"],
            tags=["precedent", "case-law"],
            memory_ids=[mid] if mid else None,
        )
        data_resp.raise_for_status()
        did = extract_id(data_resp)
        print(f"  Memory [{mid}] {prec['name']}")
        print(f"    Data: {did}")
    return memory_ids


def create_timeline(client: MemDogClient) -> list[str]:
    """Create episodic memories for the case timeline."""
    section("3. Building Case Timeline (Episodic Memories)")
    memory_ids = []
    for event in CASE_TIMELINE:
        mem_resp = client.create_memory({
            "memory_type": event["memory_type"],
            "name": event["name"],
        })
        mem_resp.raise_for_status()
        mid = extract_id(mem_resp, "memory_id")
        memory_ids.append(mid)

        data_resp = client.create_data(
            content=event["content"],
            name=event["name"],
            tags=["timeline", "case-event"],
            memory_ids=[mid] if mid else None,
        )
        data_resp.raise_for_status()
        print(f"  [{mid}] {event['name']}")
    return memory_ids


def create_entities(client: MemDogClient) -> list[str]:
    """Batch-create entities for people and organizations."""
    section("4. Creating Case Entities")
    try:
        resp = client.batch_create_entities({"entities": CASE_ENTITIES})
        resp.raise_for_status()
        result = resp.json()
        entity_ids = result.get("entity_ids", [])
        for eid, ent in zip(entity_ids, CASE_ENTITIES):
            print(f"  [{eid}] {ent['name']} ({ent['entity_type']})")
        return entity_ids
    except Exception as exc:
        print(f"  Batch create failed ({exc}), creating individually...")
        entity_ids = []
        for ent in CASE_ENTITIES:
            try:
                resp = client.batch_create_entities({"entities": [ent]})
                resp.raise_for_status()
                result = resp.json()
                eids = result.get("entity_ids", [])
                eid = eids[0] if eids else "?"
                entity_ids.append(eid)
                print(f"  [{eid}] {ent['name']} ({ent['entity_type']})")
            except Exception as inner_exc:
                print(f"  Failed: {ent['name']} -- {inner_exc}")
        return entity_ids


def compare_search_modes(client: MemDogClient) -> None:
    """Run the same query across all 5 search modes and 4 rerankers."""
    section("5. Search Mode Comparison")
    query = "Was the termination retaliatory?"

    print(f"  Query: \"{query}\"\n")
    print(f"  {'Mode':<15} {'Reranker':<15} {'Results':<8} {'Top Result'}")
    print(f"  {'-'*13:<15} {'-'*13:<15} {'-'*6:<8} {'-'*40}")

    for mode in SEARCH_MODES:
        for reranker in RERANKERS:
            try:
                resp = client.semantic_search(
                    query,
                    search_mode=mode,
                    reranker=reranker,
                    limit=3,
                )
                resp.raise_for_status()
                data = resp.json()
                results = data.get("results", data.get("items", []))
                count = len(results)
                if results:
                    top = results[0]
                    top_name = top.get("name", top.get("data_id", "?"))[:40]
                else:
                    top_name = "(none)"
                print(f"  {mode:<15} {reranker:<15} {count:<8} {top_name}")
            except Exception as exc:
                print(f"  {mode:<15} {reranker:<15} {'err':<8} {str(exc)[:40]}")


def search_and_tag(client: MemDogClient, data_ids: list[str]) -> None:
    """Search tags and add new tags to documents."""
    section("6. Tag Operations")

    # Search existing tags
    print("  Searching tags with prefix 'evidence'...")
    try:
        resp = client.search_tags("evidence", limit=10)
        resp.raise_for_status()
        tags = resp.json()
        items = tags if isinstance(tags, list) else tags.get("items", [])
        for t in items:
            if isinstance(t, str):
                print(f"    - {t}")
            else:
                print(f"    - {t.get('tag', t)}")
    except Exception as exc:
        print(f"    (error: {exc})")

    # Add a new tag to the first document
    if data_ids:
        print(f"\n  Adding tag 'key-document' to {data_ids[0]}...")
        try:
            resp = client.add_tags(data_ids[0], ["key-document", "active-case"])
            resp.raise_for_status()
            print("    Tags added successfully.")
        except Exception as exc:
            print(f"    (error: {exc})")


def explore_entity_relationships(client: MemDogClient, entity_ids: list[str]) -> None:
    """Explore relationships between case entities."""
    section("7. Entity Relationships")
    if not entity_ids:
        print("  No entities to explore.")
        return

    for eid, ent in zip(entity_ids[:3], CASE_ENTITIES[:3]):
        print(f"  Relationships for {ent['name']} [{eid}]:")
        try:
            resp = client.get_entity_relationships(eid)
            resp.raise_for_status()
            rels = resp.json()
            items = rels if isinstance(rels, list) else rels.get("relationships", [])
            if items:
                for rel in items[:5]:
                    target = rel.get("target_name", rel.get("target_id", "?"))
                    rtype = rel.get("relationship_type", rel.get("type", "?"))
                    print(f"    -> {target} ({rtype})")
            else:
                print("    (no relationships found)")
        except Exception as exc:
            print(f"    (error: {exc})")
        print()


def search_entities(client: MemDogClient) -> None:
    """Search for entities by name."""
    section("8. Entity Search")
    queries = ["Rivera", "TechCorp", "witness"]
    for q in queries:
        print(f"  Search: '{q}'")
        try:
            resp = client.search_entities(q, limit=5)
            resp.raise_for_status()
            entities = resp.json()
            items = entities if isinstance(entities, list) else []
            for ent in items:
                print(f"    - {ent.get('name', '?')} [{ent.get('entity_type', '?')}]")
            if not items:
                print("    (no results)")
        except Exception as exc:
            print(f"    (error: {exc})")
        print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Run the legal case manager demo."""
    print("Legal Case Manager -- mem-dog Example")
    print(f"API: {BASE_URL}")

    if not API_KEY:
        print("\nWARNING: MEM_DOG_API_KEY not set. Requests may fail.\n")

    client = MemDogClient(base_url=BASE_URL, api_key=API_KEY)

    # Ingest all case materials
    data_ids = ingest_documents(client)
    precedent_ids = create_precedents(client)
    timeline_ids = create_timeline(client)
    entity_ids = create_entities(client)

    # Wait for embeddings
    print("\n  Waiting 3s for embedding generation...")
    time.sleep(3)

    # Compare search modes and rerankers
    compare_search_modes(client)

    # Tag operations
    search_and_tag(client, data_ids)

    # Entity exploration
    explore_entity_relationships(client, entity_ids)
    search_entities(client)

    print("\nDone.")


if __name__ == "__main__":
    main()
