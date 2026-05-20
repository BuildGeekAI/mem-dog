"""Content Publishing Pipeline -- mem-dog example.

Multi-channel content ingestion, duplicate detection via embeddings,
editorial workflow with KV store, and tag-based categorization.

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
# Sample data: 5 articles from different channels, including 1 duplicate pair
# ---------------------------------------------------------------------------

ARTICLES = [
    {
        "title": "Announcing Our Series B Funding",
        "content": "We are thrilled to announce a $45M Series B round led by Sequoia "
                   "Capital. This investment will accelerate our AI platform development "
                   "and expand our team to 200 engineers by end of year. The round also "
                   "includes participation from existing investors Accel and Y Combinator.",
        "channel": "slack",
        "author": "ceo@example.com",
        "tags": ["announcement", "funding", "series-b"],
    },
    {
        "title": "Q2 2025 Product Roadmap",
        "content": "Key deliverables for Q2: (1) Real-time collaboration features, "
                   "(2) Enterprise SSO with SAML 2.0, (3) Advanced analytics dashboard, "
                   "(4) Mobile app beta for iOS and Android. Engineering sprints are "
                   "planned in 2-week cycles with demos every other Friday.",
        "channel": "email",
        "author": "vp-product@example.com",
        "tags": ["roadmap", "product", "q2-2025"],
    },
    {
        "title": "Engineering Best Practices Guide",
        "content": "All production code must have >80% test coverage. PRs require at "
                   "least 2 approvals. Deployments happen on Tuesdays and Thursdays via "
                   "the CI/CD pipeline. Hotfixes may deploy anytime with VP approval. "
                   "All services must expose /health and /ready endpoints.",
        "channel": "cms",
        "author": "eng-lead@example.com",
        "tags": ["engineering", "best-practices", "internal"],
    },
    {
        "title": "Customer Case Study: Acme Corp",
        "content": "Acme Corp reduced their data processing time by 73% after adopting "
                   "our platform. Their team of 15 analysts now handles 4x the volume. "
                   "Key integration points: Salesforce, Snowflake, and custom REST APIs. "
                   "Quote from CTO: 'The ROI was clear within the first month.'",
        "channel": "cms",
        "author": "marketing@example.com",
        "tags": ["case-study", "customer", "marketing"],
    },
    {
        # Duplicate of article[0], arriving via email channel
        "title": "Series B Funding Announcement",
        "content": "We are thrilled to announce a $45M Series B round led by Sequoia "
                   "Capital. This investment will accelerate our AI platform development "
                   "and expand our team to 200 engineers by end of year. The round also "
                   "includes participation from existing investors Accel and Y Combinator.",
        "channel": "email",
        "author": "pr@example.com",
        "tags": ["announcement", "funding", "press-release"],
    },
]


def setup_channels(client: MemDogClient) -> None:
    """Register channel identities and configure channels."""
    print("=" * 60)
    print("STEP 1: Setting Up Channels")
    print("=" * 60)

    channels = [
        {
            "channel_type": "slack",
            "display_name": "Slack Workspace",
            "config": {"workspace": "acme-corp", "default_channel": "#announcements"},
        },
        {
            "channel_type": "email",
            "display_name": "Corporate Email",
            "config": {"domain": "example.com", "ingest_alias": "content@example.com"},
        },
        {
            "channel_type": "cms",
            "display_name": "Internal CMS",
            "config": {"base_url": "https://cms.example.com", "api_version": "v2"},
        },
    ]

    for ch in channels:
        # Create or update channel metadata
        resp = client.update_channel(ch["channel_type"], {
            "display_name": ch["display_name"],
            "config": ch["config"],
            "status": "active",
        })
        resp.raise_for_status()
        print(f"  Configured channel: {ch['channel_type']} ({ch['display_name']})")

    # Create channel identity for the Slack author
    identity_resp = client.create_channel_identity({
        "channel_type": "slack",
        "channel_unique_id": "U12345CEO",
        "display_name": "CEO",
        "metadata": {"email": "ceo@example.com", "role": "executive"},
    })
    identity_resp.raise_for_status()
    print(f"  Created identity: slack/U12345CEO")

    # List all channels
    list_resp = client.list_channels()
    list_resp.raise_for_status()
    ch_list = list_resp.json()
    items = ch_list if isinstance(ch_list, list) else ch_list.get("channels", [])
    print(f"\n  Total channels configured: {len(items)}")


def ingest_articles(client: MemDogClient, m: MemDog) -> list[str]:
    """Ingest articles using the Universal Envelope format."""
    print("\n" + "=" * 60)
    print("STEP 2: Ingesting Articles via Universal Envelope")
    print("=" * 60)

    data_ids = []
    for i, article in enumerate(ARTICLES):
        # Build a Universal Envelope
        envelope = {
            "channel_type": article["channel"],
            "channel_unique_id": f"{article['channel']}_ingest_001",
            "sender": article["author"],
            "timestamp": datetime.now().isoformat(),
            "content_type": "text/plain",
            "body": article["content"],
            "metadata": {
                "title": article["title"],
                "tags": article["tags"],
                "source": f"{article['channel']}://content/{i+1}",
            },
        }

        resp = client.ingest(envelope, direct=True)
        resp.raise_for_status()
        result = resp.json()
        data_id = result.get("data_id") or result.get("id")
        data_ids.append(data_id)

        print(f"  [{article['channel']:5}] {article['title'][:45]}...")
        print(f"          data_id={data_id}")

    print(f"\n  Ingested {len(data_ids)} articles")
    return data_ids


def detect_duplicates(client: MemDogClient, data_ids: list[str]) -> None:
    """Create embeddings and detect duplicate content."""
    print("\n" + "=" * 60)
    print("STEP 3: Duplicate Detection via Embeddings")
    print("=" * 60)

    embedding_ids = []
    for did in data_ids:
        resp = client.create_embedding(did)
        resp.raise_for_status()
        emb = resp.json()
        emb_id = emb.get("embedding_id") or emb.get("id")
        embedding_ids.append(emb_id)
        print(f"  Created embedding for {did} -> {emb_id}")

    # Retrieve embeddings for the known duplicate pair (articles 0 and 4)
    print(f"\n  -- Comparing article 1 vs article 5 (suspected duplicate) --")
    emb1_resp = client.get_embedding(data_ids[0])
    emb1_resp.raise_for_status()
    emb1 = emb1_resp.json()

    emb5_resp = client.get_embedding(data_ids[4])
    emb5_resp.raise_for_status()
    emb5 = emb5_resp.json()

    # In a real app you would compute cosine similarity; here we show the pattern
    vec1 = emb1.get("vector") or emb1.get("embedding", [])
    vec5 = emb5.get("vector") or emb5.get("embedding", [])
    dims1 = len(vec1) if isinstance(vec1, list) else "n/a"
    dims5 = len(vec5) if isinstance(vec5, list) else "n/a"
    print(f"  Article 1 embedding: {dims1} dimensions")
    print(f"  Article 5 embedding: {dims5} dimensions")
    print(f"  (In production, compute cosine similarity; threshold > 0.95 = duplicate)")

    # Use semantic search to find similar content
    print(f"\n  -- Semantic search for 'Series B funding Sequoia' --")
    search_resp = client.semantic_search(
        "Series B funding Sequoia Capital",
        search_mode="vector",
        limit=3,
    )
    search_resp.raise_for_status()
    results = search_resp.json()
    items = results.get("results", results.get("items", []))
    if isinstance(results, list):
        items = results
    print(f"  Found {len(items)} similar articles:")
    for r in items[:3]:
        name = r.get("name", r.get("title", "untitled"))
        score = r.get("score", r.get("relevance", "n/a"))
        print(f"    - {name} (score={score})")


def manage_editorial_workflow(client: MemDogClient, data_ids: list[str]) -> None:
    """Use the KV store to track editorial workflow stages."""
    print("\n" + "=" * 60)
    print("STEP 4: Editorial Workflow (KV Store)")
    print("=" * 60)

    stages = ["draft", "review", "approved", "published"]
    titles = [a["title"] for a in ARTICLES]

    # Set initial workflow status for each article
    for i, did in enumerate(data_ids[:4]):  # skip duplicate
        key = f"article:{did}:status"
        client.set_store_value(key, {
            "stage": stages[min(i, len(stages) - 1)],
            "title": titles[i],
            "updated_by": ARTICLES[i]["author"],
            "updated_at": datetime.now().isoformat(),
        })
        print(f"  Set {key} -> stage={stages[min(i, len(stages) - 1)]}")

    # Read back a specific article's status
    print(f"\n  -- Reading workflow status --")
    sample_key = f"article:{data_ids[0]}:status"
    get_resp = client.get_store_value(sample_key)
    get_resp.raise_for_status()
    status = get_resp.json()
    print(f"  {sample_key}: {json.dumps(status, indent=4)}")

    # List all article keys
    print(f"\n  -- Listing all article workflow keys --")
    list_resp = client.list_store_keys(prefix="article:")
    list_resp.raise_for_status()
    keys = list_resp.json()
    key_list = keys if isinstance(keys, list) else keys.get("keys", [])
    print(f"  Found {len(key_list)} keys with prefix 'article:'")
    for k in key_list[:5]:
        k_name = k if isinstance(k, str) else k.get("key", str(k))
        print(f"    {k_name}")


def manage_tags(client: MemDogClient, data_ids: list[str]) -> None:
    """Demonstrate tag management for content categorization."""
    print("\n" + "=" * 60)
    print("STEP 5: Tag-Based Categorization")
    print("=" * 60)

    # Add additional tags to first article
    did = data_ids[0]
    print(f"\n  -- Adding tags to {did} --")
    add_resp = client.add_tags(did, ["featured", "homepage", "q2-2025"])
    add_resp.raise_for_status()
    print(f"  Added: featured, homepage, q2-2025")

    # Get current tags
    tags_resp = client.get_tags(did)
    tags_resp.raise_for_status()
    tags = tags_resp.json()
    tag_list = tags.get("tags", tags) if isinstance(tags, dict) else tags
    print(f"  Current tags: {tag_list}")

    # Remove a tag
    remove_resp = client.remove_tags(did, ["homepage"])
    remove_resp.raise_for_status()
    print(f"  Removed: homepage")

    # Search tags across the platform
    print(f"\n  -- Searching tags matching 'fund' --")
    search_resp = client.search_tags("fund", limit=10)
    search_resp.raise_for_status()
    found = search_resp.json()
    found_list = found if isinstance(found, list) else found.get("tags", [])
    print(f"  Matching tags: {found_list}")

    # List all tags
    all_resp = client.list_tags()
    all_resp.raise_for_status()
    all_tags = all_resp.json()
    all_list = all_tags if isinstance(all_tags, list) else all_tags.get("tags", [])
    print(f"  Total tags in system: {len(all_list)}")


def create_editorial_calendar(m: MemDog) -> None:
    """Store an editorial calendar as a custom memory."""
    print("\n" + "=" * 60)
    print("STEP 6: Editorial Calendar (Custom Memory)")
    print("=" * 60)

    calendar_content = (
        "Editorial Calendar - Q2 2025\n"
        "----------------------------\n"
        "Week 1 (Apr 7):  Series B announcement blog post\n"
        "Week 2 (Apr 14): Product roadmap public summary\n"
        "Week 3 (Apr 21): Acme Corp case study publication\n"
        "Week 4 (Apr 28): Engineering blog: scaling to 1M users\n"
        "Week 5 (May 5):  Monthly newsletter\n"
        "Week 6 (May 12): Webinar: AI in enterprise workflows\n"
        "Week 7 (May 19): Customer spotlight: Globex Corp\n"
        "Week 8 (May 26): Q2 retrospective draft\n"
    )

    result = m.add(
        calendar_content,
        memory_type="custom",
        name="Editorial Calendar Q2 2025",
        tags=["calendar", "editorial", "q2-2025"],
    )
    print(f"  Stored editorial calendar")
    print(f"  data_id={result['data_id']}")
    print(f"  memory_id={result['memory_id']}")


def main():
    """Run the content publishing pipeline demo."""
    print("Content Publishing Pipeline -- mem-dog Example")
    print(f"API: {BASE_URL}")
    print(f"Time: {datetime.now().isoformat()}")
    print()

    m = MemDog(BASE_URL, api_key=API_KEY)
    client = m.client

    # Step 1: Setup channels
    setup_channels(client)

    # Step 2: Ingest articles via Universal Envelope
    data_ids = ingest_articles(client, m)

    # Step 3: Duplicate detection via embeddings
    detect_duplicates(client, data_ids)

    # Step 4: Editorial workflow via KV store
    manage_editorial_workflow(client, data_ids)

    # Step 5: Tag management
    manage_tags(client, data_ids)

    # Step 6: Editorial calendar as custom memory
    create_editorial_calendar(m)

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Channels configured: 3 (slack, email, cms)")
    print(f"  Articles ingested:   {len(data_ids)}")
    print(f"  Duplicate pair:      articles 1 & 5")
    print(f"  Workflow stages:     draft, review, approved, published")
    print(f"  Editorial calendar:  Q2 2025")
    print("\nDone.")


if __name__ == "__main__":
    main()
