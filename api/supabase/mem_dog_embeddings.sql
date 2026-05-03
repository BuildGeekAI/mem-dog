-- mem_dog_embeddings: dedicated pgvector table for vector embeddings.
--
-- Used by STORAGE_BACKEND=supabase instead of the generic mem_dog_blobs table.
-- Stores all fields from the Embedding model as proper columns, with a native
-- `vector` column for pgvector similarity search.
--
-- Run this in Supabase SQL Editor (Dashboard → SQL Editor) or via:
--   kubectl exec -n supabase supabase-supabase-db-0 -c supabase-db -- \
--     psql -U postgres -d postgres -f /path/to/mem_dog_embeddings.sql

-- ---------------------------------------------------------------------------
-- Extension
-- ---------------------------------------------------------------------------

CREATE EXTENSION IF NOT EXISTS vector;

-- ---------------------------------------------------------------------------
-- Table
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS mem_dog_embeddings (
    embedding_id  TEXT        PRIMARY KEY,
    data_id       TEXT        NOT NULL,
    data_version  INTEGER     NOT NULL,
    version_label TEXT,
    user_id       TEXT        NOT NULL,
    ai_engine     TEXT        NOT NULL,
    model         TEXT        NOT NULL,
    dimensions    INTEGER     NOT NULL,
    chunk_index   INTEGER     NOT NULL,
    chunk_text    TEXT        NOT NULL,
    -- pgvector column (variable dimensions — no fixed size required).
    -- All vectors for a given model will share the same dimensionality at runtime.
    vector        vector,
    -- Full AISignature object stored as JSONB for future querying.
    ai_signature  JSONB,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------------------

-- Primary access pattern: get_embeddings / delete_embeddings
--   WHERE user_id = ? AND data_id = ? [AND version_label = ?]
CREATE INDEX IF NOT EXISTS mem_dog_embeddings_user_data_idx
    ON mem_dog_embeddings (user_id, data_id, version_label);

-- ---------------------------------------------------------------------------
-- pgvector HNSW index (commented out — see note below before enabling)
--
-- HNSW enables fast approximate nearest-neighbour cosine similarity search.
-- Prerequisite: all vectors stored in this table must share the same
-- dimensionality (i.e. a single embedding model is in use).  If multiple
-- models with different dimensions are stored, create one partial index per
-- model instead:
--
--   CREATE INDEX mem_dog_embeddings_hnsw_text_embedding_3_small_idx
--       ON mem_dog_embeddings USING hnsw (vector vector_cosine_ops)
--       WITH (m = 16, ef_construction = 64)
--       WHERE model = 'text-embedding-3-small';
--
-- Uncomment after confirming a single fixed-dimension model:
-- CREATE INDEX mem_dog_embeddings_hnsw_idx
--     ON mem_dog_embeddings USING hnsw (vector vector_cosine_ops)
--     WITH (m = 16, ef_construction = 64);
-- ---------------------------------------------------------------------------

-- ---------------------------------------------------------------------------
-- Grants
-- ---------------------------------------------------------------------------

GRANT ALL ON public.mem_dog_embeddings TO service_role;
GRANT ALL ON public.mem_dog_embeddings TO anon;
GRANT ALL ON public.mem_dog_embeddings TO authenticated;

-- ---------------------------------------------------------------------------
-- Row Level Security (disabled by default — service_role bypasses RLS)
-- ---------------------------------------------------------------------------

-- ALTER TABLE mem_dog_embeddings ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY user_isolation ON mem_dog_embeddings
--     USING (user_id = current_setting('app.current_user_id', true));

-- ---------------------------------------------------------------------------
-- RPC: match_embeddings — cosine similarity search with multi-tenant filter
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION match_embeddings(
    query_embedding  TEXT,
    match_count      INT  DEFAULT 5,
    filter_user_id   TEXT DEFAULT NULL,
    filter_data_ids  TEXT[] DEFAULT NULL
)
RETURNS TABLE (
    embedding_id TEXT,
    data_id      TEXT,
    chunk_text   TEXT,
    similarity   FLOAT
)
LANGUAGE sql
STABLE
AS $$
    SELECT
        e.embedding_id,
        e.data_id,
        e.chunk_text,
        1 - (e.vector <=> query_embedding::vector) AS similarity
    FROM mem_dog_embeddings e
    WHERE e.vector IS NOT NULL
      AND (filter_user_id IS NULL OR e.user_id = filter_user_id)
      AND (filter_data_ids IS NULL OR e.data_id = ANY(filter_data_ids))
    ORDER BY e.vector <=> query_embedding::vector
    LIMIT match_count;
$$;

GRANT EXECUTE ON FUNCTION match_embeddings(TEXT, INT, TEXT, TEXT[]) TO service_role;
GRANT EXECUTE ON FUNCTION match_embeddings(TEXT, INT, TEXT, TEXT[]) TO anon;
GRANT EXECUTE ON FUNCTION match_embeddings(TEXT, INT, TEXT, TEXT[]) TO authenticated;

-- ---------------------------------------------------------------------------
-- Reload PostgREST schema cache
-- ---------------------------------------------------------------------------

NOTIFY pgrst, 'reload schema';
