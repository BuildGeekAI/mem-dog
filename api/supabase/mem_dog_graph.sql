-- mem_dog_graph: entity-relationship graph tables for knowledge graph memory.
--
-- Stores entities extracted by the AI enrichment pipeline, relationships
-- between entities, and mappings from entities to source data items.
-- Uses Postgres tables in Supabase (same DB as mem_dog_embeddings).
--
-- Run this in Supabase SQL Editor or via:
--   kubectl exec -n supabase supabase-supabase-db-0 -c supabase-db -- \
--     psql -U postgres -d postgres -f /path/to/mem_dog_graph.sql

-- ---------------------------------------------------------------------------
-- Table 1: Entities
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS mem_dog_entities (
    entity_id      TEXT        PRIMARY KEY,           -- ent_<ulid>
    data_id        TEXT        NOT NULL,              -- source data item where first extracted
    user_id        TEXT        NOT NULL,
    entity_type    TEXT        NOT NULL,              -- person, organization, product, location, date, url, concept, event
    entity_name    TEXT        NOT NULL,              -- original form as extracted
    canonical_form TEXT        NOT NULL,              -- lowercased, trimmed — dedup key
    confidence     FLOAT       NOT NULL DEFAULT 1.0,  -- LLM confidence 0.0–1.0
    metadata       JSONB       NOT NULL DEFAULT '{}', -- aliases, attributes, wiki_url, etc.
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Table 2: Relationships
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS mem_dog_relationships (
    rel_id             TEXT        PRIMARY KEY,        -- rel_<ulid>
    user_id            TEXT        NOT NULL,
    data_id            TEXT        NOT NULL,           -- source data item where relationship was found
    source_entity_id   TEXT        NOT NULL REFERENCES mem_dog_entities(entity_id) ON DELETE CASCADE,
    target_entity_id   TEXT        NOT NULL REFERENCES mem_dog_entities(entity_id) ON DELETE CASCADE,
    rel_type           TEXT        NOT NULL,           -- works_at, located_in, part_of, mentions, etc.
    strength           FLOAT       NOT NULL DEFAULT 1.0,
    description        TEXT,                           -- brief LLM-generated description
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Table 3: Entity-Data Mapping (which data items mention which entities)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS mem_dog_entity_data_mapping (
    mapping_id   TEXT        PRIMARY KEY,              -- map_<ulid>
    user_id      TEXT        NOT NULL,
    entity_id    TEXT        NOT NULL REFERENCES mem_dog_entities(entity_id) ON DELETE CASCADE,
    data_id      TEXT        NOT NULL,
    mention_text TEXT,                                  -- exact text snippet that mentioned the entity
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Indexes — Entities
-- ---------------------------------------------------------------------------

-- Dedup: one canonical entity per user per type
CREATE UNIQUE INDEX IF NOT EXISTS mem_dog_entities_user_type_canonical_idx
    ON mem_dog_entities (user_id, entity_type, canonical_form);

-- Look up entities for a specific data item
CREATE INDEX IF NOT EXISTS mem_dog_entities_user_data_idx
    ON mem_dog_entities (user_id, data_id);

-- Search entities by name
CREATE INDEX IF NOT EXISTS mem_dog_entities_user_name_idx
    ON mem_dog_entities (user_id, canonical_form);

-- Filter by entity type
CREATE INDEX IF NOT EXISTS mem_dog_entities_type_idx
    ON mem_dog_entities (entity_type);

-- ---------------------------------------------------------------------------
-- Indexes — Relationships
-- ---------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS mem_dog_relationships_user_idx
    ON mem_dog_relationships (user_id);

CREATE INDEX IF NOT EXISTS mem_dog_relationships_source_idx
    ON mem_dog_relationships (source_entity_id);

CREATE INDEX IF NOT EXISTS mem_dog_relationships_target_idx
    ON mem_dog_relationships (target_entity_id);

-- One relationship of a given type between two entities per data item
CREATE UNIQUE INDEX IF NOT EXISTS mem_dog_relationships_unique_idx
    ON mem_dog_relationships (user_id, source_entity_id, target_entity_id, rel_type, data_id);

-- ---------------------------------------------------------------------------
-- Indexes — Entity-Data Mapping
-- ---------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS mem_dog_entity_data_mapping_user_entity_idx
    ON mem_dog_entity_data_mapping (user_id, entity_id);

CREATE INDEX IF NOT EXISTS mem_dog_entity_data_mapping_user_data_idx
    ON mem_dog_entity_data_mapping (user_id, data_id);

-- One mapping per entity per data item
CREATE UNIQUE INDEX IF NOT EXISTS mem_dog_entity_data_mapping_unique_idx
    ON mem_dog_entity_data_mapping (entity_id, data_id);

-- ---------------------------------------------------------------------------
-- RPC: search_entities — text search on canonical_form
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION search_entities(
    query_text       TEXT,
    filter_user_id   TEXT     DEFAULT NULL,
    filter_type      TEXT     DEFAULT NULL,
    match_count      INT      DEFAULT 20
)
RETURNS TABLE (
    entity_id      TEXT,
    entity_type    TEXT,
    entity_name    TEXT,
    canonical_form TEXT,
    confidence     FLOAT,
    data_id        TEXT,
    metadata       JSONB
)
LANGUAGE sql
STABLE
AS $$
    SELECT
        e.entity_id,
        e.entity_type,
        e.entity_name,
        e.canonical_form,
        e.confidence,
        e.data_id,
        e.metadata
    FROM mem_dog_entities e
    WHERE e.canonical_form ILIKE '%' || lower(trim(query_text)) || '%'
      AND (filter_user_id IS NULL OR e.user_id = filter_user_id)
      AND (filter_type IS NULL OR e.entity_type = filter_type)
    ORDER BY
        -- exact match first, then prefix, then substring
        CASE
            WHEN e.canonical_form = lower(trim(query_text)) THEN 0
            WHEN e.canonical_form LIKE lower(trim(query_text)) || '%' THEN 1
            ELSE 2
        END,
        e.confidence DESC,
        e.updated_at DESC
    LIMIT match_count;
$$;

-- ---------------------------------------------------------------------------
-- RPC: find_related_data — given entity IDs, find all related data_ids
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION find_related_data(
    entity_ids       TEXT[],
    filter_user_id   TEXT     DEFAULT NULL,
    match_count      INT      DEFAULT 50
)
RETURNS TABLE (
    data_id    TEXT,
    entity_id  TEXT,
    entity_name TEXT,
    entity_type TEXT
)
LANGUAGE sql
STABLE
AS $$
    SELECT DISTINCT
        m.data_id,
        e.entity_id,
        e.entity_name,
        e.entity_type
    FROM mem_dog_entity_data_mapping m
    JOIN mem_dog_entities e ON e.entity_id = m.entity_id
    WHERE m.entity_id = ANY(entity_ids)
      AND (filter_user_id IS NULL OR m.user_id = filter_user_id)
    ORDER BY m.data_id
    LIMIT match_count;
$$;

-- ---------------------------------------------------------------------------
-- Grants
-- ---------------------------------------------------------------------------

GRANT ALL ON public.mem_dog_entities TO service_role;
GRANT ALL ON public.mem_dog_entities TO anon;
GRANT ALL ON public.mem_dog_entities TO authenticated;

GRANT ALL ON public.mem_dog_relationships TO service_role;
GRANT ALL ON public.mem_dog_relationships TO anon;
GRANT ALL ON public.mem_dog_relationships TO authenticated;

GRANT ALL ON public.mem_dog_entity_data_mapping TO service_role;
GRANT ALL ON public.mem_dog_entity_data_mapping TO anon;
GRANT ALL ON public.mem_dog_entity_data_mapping TO authenticated;

GRANT EXECUTE ON FUNCTION search_entities(TEXT, TEXT, TEXT, INT) TO service_role;
GRANT EXECUTE ON FUNCTION search_entities(TEXT, TEXT, TEXT, INT) TO anon;
GRANT EXECUTE ON FUNCTION search_entities(TEXT, TEXT, TEXT, INT) TO authenticated;

GRANT EXECUTE ON FUNCTION find_related_data(TEXT[], TEXT, INT) TO service_role;
GRANT EXECUTE ON FUNCTION find_related_data(TEXT[], TEXT, INT) TO anon;
GRANT EXECUTE ON FUNCTION find_related_data(TEXT[], TEXT, INT) TO authenticated;

-- ---------------------------------------------------------------------------
-- Reload PostgREST schema cache
-- ---------------------------------------------------------------------------

NOTIFY pgrst, 'reload schema';
