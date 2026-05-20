"""Research Paper Analyzer -- mem-dog example.

Ingest papers, generate AI viewpoints, build citation graphs,
and use analysis templates for structured review.

Usage:
    export MEM_DOG_URL=http://localhost:8080
    export MEM_DOG_API_KEY=your-key
    python main.py
"""

import os
import time

from mem_dog_client import MemDogClient

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = os.environ.get("MEM_DOG_URL", "http://localhost:8080")
API_KEY = os.environ.get("MEM_DOG_API_KEY", "")

# ---------------------------------------------------------------------------
# Sample data -- research paper abstracts
# ---------------------------------------------------------------------------

PAPERS = [
    {
        "title": "Attention Is All You Need",
        "authors": ["Ashish Vaswani", "Noam Shazeer", "Niki Parmar", "Jakob Uszkoreit"],
        "institution": "Google Brain",
        "year": 2017,
        "field": "machine-learning",
        "abstract": (
            "The dominant sequence transduction models are based on complex "
            "recurrent or convolutional neural networks that include an encoder "
            "and a decoder. The best performing models also connect the encoder "
            "and decoder through an attention mechanism. We propose a new simple "
            "network architecture, the Transformer, based solely on attention "
            "mechanisms, dispensing with recurrence and convolutions entirely. "
            "Experiments on two machine translation tasks show these models to "
            "be superior in quality while being more parallelizable and requiring "
            "significantly less time to train. Our model achieves 28.4 BLEU on "
            "the WMT 2014 English-to-German translation task, improving over the "
            "existing best results by over 2 BLEU. On the English-to-French task, "
            "our model establishes a new single-model state-of-the-art BLEU score "
            "of 41.8 after training for 3.5 days on eight GPUs."
        ),
        "tags": ["paper", "machine-learning", "transformer", "attention", "nlp"],
    },
    {
        "title": "BERT: Pre-training of Deep Bidirectional Transformers",
        "authors": ["Jacob Devlin", "Ming-Wei Chang", "Kenton Lee", "Kristina Toutanova"],
        "institution": "Google AI Language",
        "year": 2019,
        "field": "natural-language-processing",
        "abstract": (
            "We introduce a new language representation model called BERT, which "
            "stands for Bidirectional Encoder Representations from Transformers. "
            "Unlike recent language representation models, BERT is designed to "
            "pre-train deep bidirectional representations from unlabeled text by "
            "jointly conditioning on both left and right context in all layers. "
            "As a result, the pre-trained BERT model can be fine-tuned with just "
            "one additional output layer to create state-of-the-art models for a "
            "wide range of tasks, such as question answering and language inference, "
            "without substantial task-specific architecture modifications. BERT "
            "obtains new state-of-the-art results on eleven natural language "
            "processing benchmarks."
        ),
        "tags": ["paper", "natural-language-processing", "bert", "pre-training", "transformers"],
    },
    {
        "title": "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks",
        "authors": ["Patrick Lewis", "Ethan Perez", "Aleksandra Piktus", "Fabio Petroni"],
        "institution": "Meta AI / University College London",
        "year": 2020,
        "field": "information-retrieval",
        "abstract": (
            "Large pre-trained language models have been shown to store factual "
            "knowledge in their parameters, and achieve state-of-the-art results "
            "when fine-tuned on downstream NLP tasks. However, their ability to "
            "access and precisely manipulate knowledge is still limited. We explore "
            "a general-purpose fine-tuning recipe for retrieval-augmented generation "
            "(RAG) -- models which combine pre-trained parametric and non-parametric "
            "memory to generate responses. We find that RAG models generate more "
            "specific, diverse, and factual language than a state-of-the-art "
            "parametric-only seq2seq baseline. RAG models achieve state-of-the-art "
            "results on three open-domain QA tasks, outperforming parametric "
            "seq2seq models and task-specific retrieve-and-extract architectures."
        ),
        "tags": ["paper", "information-retrieval", "rag", "knowledge-graph", "qa"],
    },
    {
        "title": "Graph Neural Networks: A Review of Methods and Applications",
        "authors": ["Jie Zhou", "Ganqu Cui", "Shengding Hu", "Zhengyan Zhang"],
        "institution": "Tsinghua University",
        "year": 2020,
        "field": "graph-ml",
        "abstract": (
            "Lots of learning tasks require dealing with graph data which contains "
            "rich relation information among elements. Modeling physics systems, "
            "learning molecular fingerprints, predicting protein interfaces, and "
            "classifying diseases require models to learn from graph inputs. Graph "
            "neural networks (GNNs) are neural models that capture the dependence "
            "of graphs via message passing between the nodes. In recent years, "
            "variants of GNNs such as graph convolutional networks (GCN), graph "
            "attention networks (GAT), and graph recurrent networks have demonstrated "
            "ground-breaking performance on many deep learning tasks. This paper "
            "provides a comprehensive overview of graph neural networks in data "
            "mining and machine learning fields."
        ),
        "tags": ["paper", "graph-ml", "gnn", "knowledge-graph", "survey"],
    },
]

# Viewpoint templates for each paper
VIEWPOINT_TEMPLATES = [
    {"name": "Key Findings", "description": "Main contributions and results of the paper"},
    {"name": "Methodology", "description": "Research methods, experimental setup, and approach"},
    {"name": "Limitations & Future Work", "description": "Acknowledged limitations and suggested future directions"},
]


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


# ---------------------------------------------------------------------------
# Main workflow
# ---------------------------------------------------------------------------

def ingest_papers(client: MemDogClient) -> list[dict]:
    """Store paper abstracts and create semantic memories for topic clusters."""
    section("1. Ingesting Research Papers")
    paper_records = []

    # Track unique fields for topic memories
    topic_memories = {}

    for paper in PAPERS:
        # Create or reuse topic memory
        field = paper["field"]
        if field not in topic_memories:
            print(f"  Creating topic memory: {field}...")
            try:
                resp = client.create_memory({
                    "memory_type": "semantic",
                    "name": f"Topic: {field.replace('-', ' ').title()}",
                    "description": f"Papers and research in {field}",
                })
                resp.raise_for_status()
                mid = extract_id(resp, "memory_id")
                topic_memories[field] = mid
                print(f"    Memory ID: {mid}")
            except Exception as exc:
                print(f"    (error: {exc})")
                topic_memories[field] = None

        # Store paper abstract
        full_content = (
            f"Title: {paper['title']}\n"
            f"Authors: {', '.join(paper['authors'])}\n"
            f"Institution: {paper['institution']}\n"
            f"Year: {paper['year']}\n\n"
            f"Abstract:\n{paper['abstract']}"
        )

        mid = topic_memories.get(field)
        try:
            resp = client.create_data(
                content=full_content,
                name=paper["title"],
                tags=paper["tags"],
                memory_ids=[mid] if mid else None,
            )
            resp.raise_for_status()
            did = extract_id(resp)
            record = {"data_id": did, "title": paper["title"], "paper": paper}
            paper_records.append(record)
            print(f"  [{did}] {paper['title']} ({paper['year']})")
            print(f"           topic: {field}, tags: {paper['tags']}")
        except Exception as exc:
            print(f"  (error storing {paper['title']}: {exc})")
            paper_records.append({"data_id": None, "title": paper["title"], "paper": paper})

    return paper_records


def create_viewpoints(client: MemDogClient, paper_records: list[dict]) -> dict[str, list[str]]:
    """Create AI viewpoints for each paper."""
    section("2. Creating AI Viewpoints")
    viewpoint_map = {}  # data_id -> [viewpoint_ids]

    for record in paper_records:
        did = record["data_id"]
        if not did:
            continue

        title = record["title"]
        print(f"  Viewpoints for: {title}")
        vp_ids = []

        for template in VIEWPOINT_TEMPLATES:
            try:
                resp = client.create_viewpoint({
                    "data_id": did,
                    "name": template["name"],
                    "description": template["description"],
                })
                resp.raise_for_status()
                data = resp.json()
                vp_id = data.get("viewpoint_id") or data.get("id")
                vp_ids.append(vp_id)
                print(f"    [{vp_id}] {template['name']}")
            except Exception as exc:
                print(f"    (error creating '{template['name']}': {exc})")

        viewpoint_map[did] = vp_ids

    return viewpoint_map


def inspect_viewpoints(client: MemDogClient, viewpoint_map: dict[str, list[str]], paper_records: list[dict]) -> None:
    """List and inspect viewpoint details and history."""
    section("3. Inspecting Viewpoints")

    # List viewpoints for each paper
    for record in paper_records:
        did = record["data_id"]
        if not did:
            continue

        print(f"  Viewpoints for: {record['title']}")
        try:
            resp = client.get_data_viewpoints(did)
            resp.raise_for_status()
            viewpoints = resp.json()
            items = viewpoints if isinstance(viewpoints, list) else viewpoints.get("viewpoints", viewpoints.get("items", []))
            for vp in items:
                vp_id = vp.get("viewpoint_id", vp.get("id", "?"))
                name = vp.get("name", "?")
                content = vp.get("content", vp.get("text", ""))
                preview = str(content)[:100] + "..." if len(str(content)) > 100 else str(content)
                print(f"    [{vp_id}] {name}")
                if preview:
                    print(f"      {preview}")
        except Exception as exc:
            print(f"    (error: {exc})")
        print()

    # Check viewpoint history for the first paper's first viewpoint
    first_vps = next((vps for vps in viewpoint_map.values() if vps), [])
    if first_vps:
        vp_id = first_vps[0]
        print(f"  Version history for viewpoint {vp_id}:")
        try:
            resp = client.get_viewpoint_history(vp_id)
            resp.raise_for_status()
            history = resp.json()
            items = history if isinstance(history, list) else history.get("versions", history.get("items", []))
            for ver in items:
                version = ver.get("version", "?")
                created = ver.get("created_at", "?")
                print(f"    v{version} -- {created}")
            if not items:
                print("    (single version)")
        except Exception as exc:
            print(f"    (error: {exc})")


def setup_analysis_templates(client: MemDogClient) -> list[str]:
    """Seed default templates and create a custom paper review template."""
    section("4. Analysis Templates")

    # Seed default templates
    print("  Seeding default analysis templates...")
    try:
        resp = client.seed_analysis_templates()
        resp.raise_for_status()
        data = resp.json()
        count = data.get("count", data.get("seeded", "?"))
        print(f"    Seeded {count} default templates.")
    except Exception as exc:
        print(f"    (error: {exc})")

    # List existing templates
    print("\n  Existing templates:")
    template_ids = []
    try:
        resp = client.list_analysis_templates()
        resp.raise_for_status()
        templates = resp.json()
        items = templates if isinstance(templates, list) else templates.get("templates", templates.get("items", []))
        for tmpl in items[:8]:
            tid = tmpl.get("template_id", tmpl.get("id", "?"))
            name = tmpl.get("name", "?")
            template_ids.append(tid)
            print(f"    [{tid}] {name}")
        if not items:
            print("    (none found)")
    except Exception as exc:
        print(f"    (error: {exc})")

    # Create custom template for paper review
    print("\n  Creating custom 'Paper Review' template...")
    try:
        resp = client.create_analysis_template({
            "name": "Paper Review",
            "description": "Structured review template for academic papers",
            "data_type": "text",
            "sections": [
                {"name": "Summary", "prompt": "Summarize the paper in 2-3 sentences."},
                {"name": "Novelty", "prompt": "What is novel about this approach?"},
                {"name": "Methodology", "prompt": "Describe the methodology and experimental setup."},
                {"name": "Strengths", "prompt": "List the main strengths of this work."},
                {"name": "Weaknesses", "prompt": "List potential weaknesses or limitations."},
                {"name": "Impact", "prompt": "What is the expected impact on the field?"},
            ],
        })
        resp.raise_for_status()
        data = resp.json()
        tid = data.get("template_id") or data.get("id")
        print(f"    Created: {tid}")
        template_ids.append(tid)
    except Exception as exc:
        print(f"    (error: {exc})")

    return template_ids


def create_author_entities(client: MemDogClient, paper_records: list[dict]) -> list[str]:
    """Batch-create entities for authors and institutions."""
    section("5. Building Author & Institution Graph")

    entities = []
    seen_names = set()

    for record in paper_records:
        paper = record["paper"]

        # Authors
        for author in paper["authors"]:
            if author not in seen_names:
                entities.append({
                    "name": author,
                    "entity_type": "person",
                    "properties": {
                        "role": "author",
                        "institution": paper["institution"],
                        "field": paper["field"],
                    },
                })
                seen_names.add(author)

        # Institutions
        inst = paper["institution"]
        if inst not in seen_names:
            entities.append({
                "name": inst,
                "entity_type": "organization",
                "properties": {
                    "type": "research-institution",
                    "fields": [paper["field"]],
                },
            })
            seen_names.add(inst)

    print(f"  Creating {len(entities)} entities (authors + institutions)...")
    entity_ids = []
    try:
        resp = client.batch_create_entities({"entities": entities})
        resp.raise_for_status()
        result = resp.json()
        entity_ids = result.get("entity_ids", [])
        for eid, ent in zip(entity_ids, entities):
            print(f"    [{eid}] {ent['name']} ({ent['entity_type']})")
    except Exception as exc:
        print(f"    Batch failed ({exc}), creating individually...")
        for ent in entities:
            try:
                resp = client.batch_create_entities({"entities": [ent]})
                resp.raise_for_status()
                result = resp.json()
                eids = result.get("entity_ids", [])
                eid = eids[0] if eids else "?"
                entity_ids.append(eid)
                print(f"    [{eid}] {ent['name']} ({ent['entity_type']})")
            except Exception as inner_exc:
                print(f"    Failed: {ent['name']} -- {inner_exc}")

    return entity_ids


def explore_citation_graph(client: MemDogClient, entity_ids: list[str]) -> None:
    """Explore relationships between authors and institutions."""
    section("6. Exploring Citation Graph")
    if not entity_ids:
        print("  No entities to explore.")
        return

    for eid in entity_ids[:4]:
        try:
            # Get entity details
            resp = client.get_entity(eid)
            resp.raise_for_status()
            entity = resp.json()
            name = entity.get("name", "?")

            print(f"  {name} [{eid}]:")

            # Get relationships
            rel_resp = client.get_entity_relationships(eid)
            rel_resp.raise_for_status()
            rels = rel_resp.json()
            items = rels if isinstance(rels, list) else rels.get("relationships", [])
            if items:
                for rel in items[:5]:
                    target = rel.get("target_name", rel.get("target_id", "?"))
                    rtype = rel.get("relationship_type", rel.get("type", "?"))
                    print(f"    -> {target} ({rtype})")
            else:
                print("    (no relationships found)")
        except Exception as exc:
            print(f"    (error for {eid}: {exc})")
        print()


def graph_search(client: MemDogClient) -> None:
    """Use graph search mode to explore concepts across papers."""
    section("7. Graph-Based Concept Search")
    queries = [
        "How does the transformer architecture relate to language models?",
        "What is retrieval-augmented generation and how does it improve factual accuracy?",
        "Compare graph neural networks with attention mechanisms",
        "What are the key advances in pre-training methods?",
    ]

    for query in queries:
        print(f"  Q: {query}")
        try:
            resp = client.semantic_search(query, search_mode="graph", limit=3)
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", data.get("items", []))
            if results:
                for i, r in enumerate(results, 1):
                    name = r.get("name", r.get("data_id", "?"))
                    score = r.get("score", r.get("relevance", "?"))
                    print(f"    {i}. {name} (score={score})")
            else:
                print("    (no results)")
        except Exception as exc:
            print(f"    (error: {exc})")
        print()


def search_entities_demo(client: MemDogClient) -> None:
    """Search for specific entities by name."""
    section("8. Entity Search")
    queries = ["Vaswani", "Google", "Tsinghua", "transformer"]
    for q in queries:
        print(f"  Search: '{q}'")
        try:
            resp = client.search_entities(q, limit=5)
            resp.raise_for_status()
            entities = resp.json()
            items = entities if isinstance(entities, list) else []
            for ent in items:
                name = ent.get("name", "?")
                etype = ent.get("entity_type", "?")
                props = ent.get("properties", {})
                print(f"    - {name} [{etype}] {props}")
            if not items:
                print("    (no results)")
        except Exception as exc:
            print(f"    (error: {exc})")
        print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Run the research paper analyzer demo."""
    print("Research Paper Analyzer -- mem-dog Example")
    print(f"API: {BASE_URL}")

    if not API_KEY:
        print("\nWARNING: MEM_DOG_API_KEY not set. Requests may fail.\n")

    client = MemDogClient(base_url=BASE_URL, api_key=API_KEY)

    # Step 1: Ingest papers with topic memories
    paper_records = ingest_papers(client)

    # Step 2: Create viewpoints for each paper
    viewpoint_map = create_viewpoints(client, paper_records)

    # Step 3: Inspect viewpoints
    inspect_viewpoints(client, viewpoint_map, paper_records)

    # Step 4: Analysis templates
    template_ids = setup_analysis_templates(client)

    # Step 5: Build author/institution entity graph
    entity_ids = create_author_entities(client, paper_records)

    # Wait for embeddings
    print("\n  Waiting 3s for embedding generation...")
    time.sleep(3)

    # Step 6: Explore citation graph
    explore_citation_graph(client, entity_ids)

    # Step 7: Graph-based concept search
    graph_search(client)

    # Step 8: Entity search
    search_entities_demo(client)

    print("\nDone.")


if __name__ == "__main__":
    main()
