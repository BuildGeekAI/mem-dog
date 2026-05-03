# Graph Memory

Dual-layer knowledge graph: Postgres entity tables (zero-infra) + optional Graphiti temporal knowledge graph (Neo4j).

## Architecture

```
Data Ingest → Webhook Pipeline → Entity Extraction
                                       │
                                       ├─→ Postgres (mem_dog_entities, mem_dog_relationships)
                                       │   └─ Entity-aware RAG, SQL joins with pgvector
                                       │
                                       └─→ Graphiti + Neo4j (optional)
                                           └─ Temporal facts, BFS traversal, graph search
```

**Postgres layer** (always active): 3 tables for entities, relationships, and entity-data mappings. Zero new infra.

**Graphiti layer** (optional, requires `NEO4J_URI`): Temporal knowledge graph with episodic nodes, entity resolution, and fact evolution. Powered by [Graphiti](https://github.com/getzep/graphiti) (Zep's open-source engine, Apache 2.0).

## Schema (Postgres)

3 tables in the same Supabase database as `mem_dog_embeddings`:

| Table | Purpose |
|-------|---------|
| `mem_dog_entities` | Extracted entities (person, org, product, location, date, url, concept, event) |
| `mem_dog_relationships` | Directed relationships between entities (works_at, part_of, mentions, etc.) |
| `mem_dog_entity_data_mapping` | Which data items mention which entities |

**Dedup:** Unique index on `(user_id, entity_type, canonical_form)` — same entity is never stored twice per user.

**Migration:** `api/supabase/mem_dog_graph.sql`

## How Entities Get Created

The webhook pipeline extracts entities automatically during AI enrichment:

1. LLM prompt includes `typed_entities` and `relationships` fields in the JSON schema
2. After viewpoint + auto-tagging, `_write_api_results_async()` calls `POST /api/v1/graph/entities/batch`
3. Entities are upserted (deduped by canonical form), relationships created, and entity-data mappings stored
4. **Dual-write**: If Graphiti is enabled, the same entities/relationships are also ingested as a Graphiti episode (fire-and-forget, never blocks the response)

For direct ingestion (`POST /api/v1/ingest` with `direct=true`), text content is also fed to Graphiti as a raw episode so it can extract its own entities with temporal awareness.

## Search Modes

The `/api/v1/ai/query/semantic` and `/api/v1/ai/query/chat` endpoints support 5 search modes:

| Mode | Engine | Description |
|------|--------|-------------|
| `vector` | pgvector | Cosine similarity only (default, backward compatible) |
| `fts` | Postgres | BM25 full-text keyword search (no embedding needed) |
| `hybrid` | pgvector + Postgres | Cosine + BM25 merged with Reciprocal Rank Fusion (RRF) |
| `graph` | Graphiti + Neo4j | BFS traversal + semantic + BM25 on knowledge graph |
| `full` | All | pgvector hybrid + Graphiti graph in parallel, merged with RRF |

### Reranking

4 strategies available via `rerank.method`:

| Method | Description |
|--------|-------------|
| `none` | No reranking (default) |
| `rrf` | Reciprocal Rank Fusion — merge multiple ranked lists |
| `mmr` | Maximal Marginal Relevance — balance relevance vs diversity |
| `cross_encoder` | LLM-based relevance scoring via model server |

### Temporal Filtering

When using `graph` or `full` mode, the `temporal` parameter enables point-in-time queries:

```json
{
  "query": "Who is the CEO of Acme?",
  "search_mode": "graph",
  "temporal": {
    "valid_at": "2025-06-01T00:00:00Z"
  }
}
```

## API Endpoints

### Entity CRUD (Postgres)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/graph/entities?q=&user_id=` | Search entities by name |
| GET | `/api/v1/graph/entities/{id}` | Entity detail |
| GET | `/api/v1/graph/entities/{id}/relationships` | Entity relationships |
| GET | `/api/v1/graph/data/{data_id}/entities` | Entities in a data item |
| POST | `/api/v1/graph/entities/batch` | Batch create (webhook pipeline) |
| DELETE | `/api/v1/graph/entities/{id}` | Delete entity + cascade |
| DELETE | `/api/v1/graph/data/{data_id}/entities` | Delete all entities for data item |

### Temporal Facts (Graphiti — requires Neo4j)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/graph/facts?q=&at=` | Query temporal facts (optional point-in-time) |
| GET | `/api/v1/graph/facts/timeline?entity_id=` | Fact history for an entity |

## Entity-Aware RAG

The `POST /api/v1/ai/query/chat` endpoint automatically enhances search with graph context:

1. Search (mode-dependent) for top-N results
2. Match entity names from query against user's entity table
3. Add "Known entities" hint to the LLM system prompt
4. Result: better answers when queries reference specific people, orgs, or concepts

## Python SDK

```python
from mem_dog_client import MemDog

m = MemDog("http://localhost:8080", user_id="user1")

# Search entities
entities = m.entities("Google")
# → [{"entity_id": "ent_...", "entity_type": "organization", "entity_name": "Google", ...}]

# Get entities linked to a data item
linked = m.related("data_01ABC...")
# → [{"entity_id": "ent_...", "entity_type": "person", "entity_name": "John Smith", ...}]
```

## Infrastructure

### Local Development

Neo4j is included in `docker-compose.yml`:
- Browser: http://localhost:7474
- Bolt: bolt://localhost:7687
- Credentials: neo4j/memdog_neo4j

### Production (GKE)

Kubernetes manifests in `k8s/neo4j/`:
- Namespace: `neo4j`
- PVC: 10Gi for data persistence
- Service: ClusterIP on ports 7687 (bolt) and 7474 (http)

API env vars:
- `NEO4J_URI=bolt://neo4j.neo4j.svc.cluster.local:7687`
- `NEO4J_USER=neo4j`
- `NEO4J_PASSWORD=<from neo4j-secret>`

### Without Neo4j

If `NEO4J_URI` is not set:
- Postgres entity tables work normally
- `search_mode: "graph"` and `search_mode: "full"` return HTTP 400
- `search_mode: "vector"`, `"fts"`, `"hybrid"` work without Neo4j
- Temporal endpoints (`/api/v1/graph/facts`) return HTTP 400

## Design Decisions

- **Dual-layer (Postgres + Neo4j):** Postgres entities are zero-infra and provide entity-aware RAG. Graphiti/Neo4j adds temporal reasoning, BFS traversal, and community detection for advanced use cases. Both receive data via dual-write.
- **Graphiti over custom Neo4j:** Graphiti (Zep's open-source engine) handles entity resolution, fact evolution, and temporal awareness out of the box. Apache 2.0 licensed.
- **Gemini as Graphiti LLM:** Reuses the existing `SYSTEM_GEMINI_API_KEY` — no new API key needed.
- **Fire-and-forget dual-write:** Graphiti ingestion is non-blocking (`asyncio.create_task`). Never blocks the API response or webhook pipeline.
- **BM25 on pgvector:** Full-text search via `tsvector` column on `mem_dog_embeddings`, exposed through `match_embeddings_hybrid` and `match_embeddings_fts` RPCs. Migration: `api/supabase/mem_dog_embeddings_fts.sql`.
- **Canonical form:** `entity_name.strip().lower()` for dedup — "Google LLC" and "google llc" map to the same entity.
