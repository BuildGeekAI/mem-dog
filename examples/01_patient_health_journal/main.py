"""Patient Health Journal -- mem-dog example.

Record daily symptoms, vitals, and medication. Query health history
with AI-powered search and explore extracted medical entities.

Usage:
    export MEM_DOG_URL=http://localhost:8080
    export MEM_DOG_API_KEY=your-key
    python main.py
"""

import os
import sys
import time

from mem_dog_client import MemDog

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = os.environ.get("MEM_DOG_URL", "http://localhost:8080")
API_KEY = os.environ.get("MEM_DOG_API_KEY", "")

# ---------------------------------------------------------------------------
# Sample data -- daily health journal entries
# ---------------------------------------------------------------------------

PATIENT_PROFILE = (
    "Patient: Sarah Chen, Age 42, Female. "
    "Known conditions: migraine with aura, mild hypertension. "
    "Current medications: Sumatriptan 50mg PRN, Lisinopril 10mg daily. "
    "Allergies: Penicillin (rash), Sulfa drugs. "
    "Primary care physician: Dr. Emily Park."
)

JOURNAL_ENTRIES = [
    {
        "date": "2026-05-10",
        "content": (
            "2026-05-10: Woke up with a mild headache behind the left eye. "
            "Blood pressure 128/82. Took morning Lisinopril. No aura. "
            "Headache resolved by noon without Sumatriptan. "
            "Slept 7 hours, mood fair."
        ),
        "tags": ["headache", "vitals", "morning"],
    },
    {
        "date": "2026-05-11",
        "content": (
            "2026-05-11: Felt great today. Blood pressure 122/78. "
            "30-minute walk in the park. No headache. "
            "Started tracking water intake -- drank 2.5L. "
            "Slept 8 hours, mood good."
        ),
        "tags": ["vitals", "exercise", "hydration"],
    },
    {
        "date": "2026-05-12",
        "content": (
            "2026-05-12: Migraine with aura started at 2pm. "
            "Visual disturbance (zigzag lines) for 20 minutes, "
            "then severe throbbing headache on the left side. "
            "Took Sumatriptan 50mg at 2:30pm. Nausea but no vomiting. "
            "Pain subsided by 5pm. Blood pressure 135/88 before medication. "
            "Possible trigger: skipped lunch, stared at screen all morning."
        ),
        "tags": ["migraine", "aura", "sumatriptan", "trigger"],
    },
    {
        "date": "2026-05-13",
        "content": (
            "2026-05-13: Post-migraine fatigue. Mild residual headache. "
            "Blood pressure 130/84. Took it easy, worked from home. "
            "Drank 3L water. Ate regular meals. "
            "Slept 9 hours, mood low."
        ),
        "tags": ["post-migraine", "fatigue", "vitals"],
    },
    {
        "date": "2026-05-14",
        "content": (
            "2026-05-14: Feeling better. Blood pressure 124/80. "
            "Noticed mild neck stiffness, did some stretches. "
            "No headache. 20-minute yoga session. "
            "Slept 7.5 hours, mood improving."
        ),
        "tags": ["vitals", "exercise", "recovery"],
    },
    {
        "date": "2026-05-15",
        "content": (
            "2026-05-15: Good day overall. Blood pressure 120/76 -- best this week. "
            "No headache, no symptoms. 45-minute brisk walk. "
            "Dr. Park called -- lab results normal, cholesterol 195. "
            "Slept 8 hours, mood good."
        ),
        "tags": ["vitals", "exercise", "labs", "cholesterol"],
    },
    {
        "date": "2026-05-16",
        "content": (
            "2026-05-16: Woke up with sinus pressure and mild congestion. "
            "Blood pressure 126/80. Seasonal allergies flaring up. "
            "Took cetirizine 10mg. No migraine symptoms. "
            "Worked from home. Slept 7 hours, mood fair."
        ),
        "tags": ["allergies", "sinus", "vitals"],
    },
    {
        "date": "2026-05-17",
        "content": (
            "2026-05-17: Headache returned, right temple this time. "
            "Blood pressure 132/86. Felt stressed about work deadline. "
            "No aura, so likely tension headache not migraine. "
            "Took ibuprofen 400mg. Headache eased in 1 hour. "
            "Need to manage stress better. Slept 6 hours, mood anxious."
        ),
        "tags": ["headache", "tension", "stress", "vitals"],
    },
    {
        "date": "2026-05-18",
        "content": (
            "2026-05-18: Tried a new meditation app for 15 minutes. "
            "Blood pressure 118/74 -- lowest reading in weeks. "
            "No headache. Felt calm and focused. "
            "45-minute hike. Ate well. Slept 8.5 hours, mood great."
        ),
        "tags": ["meditation", "vitals", "exercise", "mental-health"],
    },
    {
        "date": "2026-05-19",
        "content": (
            "2026-05-19: Monthly follow-up with Dr. Park. "
            "Discussed migraine frequency -- 2 episodes this month, down from 4 last month. "
            "Blood pressure average improving. She suggested continuing current meds, "
            "adding magnesium 400mg supplement. Next appointment June 19. "
            "Slept 7 hours, mood positive."
        ),
        "tags": ["appointment", "vitals", "medication-change", "magnesium"],
    },
]

# Queries to demonstrate search capabilities
DEMO_QUERIES = [
    "When did the headaches start and what were the triggers?",
    "What medications am I currently taking?",
    "Show my blood pressure trend over the past week",
    "What happened during my last migraine episode?",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def section(title: str) -> None:
    """Print a section header."""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}\n")


def safe_json(response_data: dict, key: str, default="N/A"):
    """Safely extract a key from a response dict."""
    return response_data.get(key, default)


# ---------------------------------------------------------------------------
# Main workflow
# ---------------------------------------------------------------------------

def ingest_patient_profile(m: MemDog) -> str:
    """Store the patient profile as a long-term user memory."""
    section("1. Storing Patient Profile")
    result = m.add(
        PATIENT_PROFILE,
        name="Patient Profile - Sarah Chen",
        memory_type="user",
        tags=["profile", "patient-info"],
    )
    data_id = result["data_id"]
    print(f"  Stored patient profile: {data_id}")
    print(f"  Memory ID:              {result.get('memory_id', 'N/A')}")
    return data_id


def ingest_journal_entries(m: MemDog) -> list[str]:
    """Store daily health journal entries as timeline memories."""
    section("2. Ingesting Daily Journal Entries")
    data_ids = []
    for entry in JOURNAL_ENTRIES:
        result = m.add(
            entry["content"],
            name=f"Health Journal - {entry['date']}",
            memory_type="timeline",
            tags=entry["tags"],
        )
        did = result["data_id"]
        data_ids.append(did)
        print(f"  [{entry['date']}] Stored as {did}  tags={entry['tags']}")
    print(f"\n  Total entries stored: {len(data_ids)}")
    return data_ids


def retrieve_single_entry(m: MemDog, data_id: str) -> None:
    """Retrieve and display a single journal entry by ID."""
    section("3. Retrieving a Single Entry")
    try:
        item = m.get(data_id)
        print(f"  Data ID:    {item.get('data_id', data_id)}")
        print(f"  Name:       {item.get('name', 'N/A')}")
        print(f"  Tags:       {item.get('tags', [])}")
        content = item.get("content", "")
        if isinstance(content, str):
            preview = content[:200] + ("..." if len(content) > 200 else "")
        else:
            preview = str(content)[:200]
        print(f"  Content:    {preview}")
    except Exception as exc:
        print(f"  Error retrieving entry: {exc}")


def run_ai_queries(m: MemDog) -> None:
    """Run AI-powered RAG queries against the health journal."""
    section("4. AI-Powered Health Queries")
    for query in DEMO_QUERIES:
        print(f"  Q: {query}")
        try:
            results = m.search(query, use_ai=True)
            if results:
                answer = results[0]
                response_text = answer.get("response", answer.get("answer", str(answer)))
                if isinstance(response_text, str):
                    # Truncate long responses for readability
                    preview = response_text[:300] + ("..." if len(response_text) > 300 else "")
                    print(f"  A: {preview}")
                else:
                    print(f"  A: {response_text}")
                sources = answer.get("sources", [])
                if sources:
                    print(f"     Sources: {len(sources)} document(s) referenced")
            else:
                print("  A: (no results)")
        except Exception as exc:
            print(f"  A: (error: {exc})")
        print()


def explore_entities(m: MemDog) -> None:
    """Search for medical entities extracted from journal entries."""
    section("5. Exploring Medical Entities")
    entity_queries = [
        ("migraine", "concept"),
        ("Sumatriptan", "concept"),
        ("Dr. Park", "person"),
        ("blood pressure", "concept"),
    ]
    for query, etype in entity_queries:
        print(f"  Searching entities: '{query}' (type={etype})")
        try:
            entities = m.entities(query, entity_type=etype, limit=5)
            if entities:
                for ent in entities:
                    print(f"    - {ent.get('name', 'N/A')} "
                          f"[{ent.get('entity_type', '?')}] "
                          f"id={ent.get('entity_id', ent.get('id', '?'))}")
            else:
                print("    (no entities found)")
        except Exception as exc:
            print(f"    (error: {exc})")
        print()


def explore_related_entities(m: MemDog, data_id: str) -> None:
    """Show entities extracted from a specific journal entry."""
    section("6. Related Entities for a Single Entry")
    print(f"  Data ID: {data_id}")
    try:
        related = m.related(data_id)
        if related:
            for ent in related:
                print(f"    - {ent.get('name', 'N/A')} "
                      f"[{ent.get('entity_type', '?')}] "
                      f"relationship={ent.get('relationship', 'linked')}")
        else:
            print("  (no related entities found)")
    except Exception as exc:
        print(f"  (error: {exc})")


def cleanup(m: MemDog, data_ids: list[str], profile_id: str) -> None:
    """Delete all created data items (optional cleanup)."""
    section("7. Cleanup (Optional)")
    print(f"  Would delete {len(data_ids) + 1} items.")
    print("  Skipping cleanup so data persists for exploration.")
    print("  To delete, uncomment the cleanup loop below.")
    # Uncomment to actually delete:
    # for did in data_ids + [profile_id]:
    #     try:
    #         m.delete(did)
    #         print(f"    Deleted {did}")
    #     except Exception as exc:
    #         print(f"    Failed to delete {did}: {exc}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Run the patient health journal demo."""
    print("Patient Health Journal -- mem-dog Example")
    print(f"API: {BASE_URL}")

    if not API_KEY:
        print("\nWARNING: MEM_DOG_API_KEY not set. Requests may fail.\n")

    m = MemDog(BASE_URL, api_key=API_KEY)

    # Step 1: Store patient profile
    profile_id = ingest_patient_profile(m)

    # Step 2: Ingest daily journal entries
    data_ids = ingest_journal_entries(m)

    # Brief pause to allow embeddings to generate
    print("\n  Waiting 2s for embedding generation...")
    time.sleep(2)

    # Step 3: Retrieve a single entry (the migraine episode)
    retrieve_single_entry(m, data_ids[2])  # May 12 migraine entry

    # Step 4: AI-powered queries
    run_ai_queries(m)

    # Step 5: Explore medical entities
    explore_entities(m)

    # Step 6: Related entities for the migraine entry
    explore_related_entities(m, data_ids[2])

    # Step 7: Cleanup
    cleanup(m, data_ids, profile_id)

    print("\nDone.")


if __name__ == "__main__":
    main()
