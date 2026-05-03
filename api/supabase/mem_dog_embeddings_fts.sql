-- BM25-style full-text search on mem_dog_embeddings
-- Adds tsvector column and hybrid search RPCs for Zep-like multi-signal search.

-- 1. Add tsvector column (auto-generated from chunk_text)
ALTER TABLE mem_dog_embeddings
    ADD COLUMN IF NOT EXISTS chunk_tsv tsvector
    GENERATED ALWAYS AS (to_tsvector('english', coalesce(chunk_text, ''))) STORED;

CREATE INDEX IF NOT EXISTS mem_dog_embeddings_chunk_tsv_idx
    ON mem_dog_embeddings USING gin (chunk_tsv);

-- 2. Hybrid search RPC: cosine similarity + BM25 merged with RRF
CREATE OR REPLACE FUNCTION match_embeddings_hybrid(
    query_embedding TEXT,
    query_text TEXT,
    match_count INT DEFAULT 5,
    filter_user_id TEXT DEFAULT NULL,
    filter_data_ids TEXT[] DEFAULT NULL,
    vector_weight FLOAT DEFAULT 0.5,
    fts_weight FLOAT DEFAULT 0.5,
    rrf_k INT DEFAULT 60
)
RETURNS TABLE (
    embedding_id TEXT,
    data_id TEXT,
    chunk_text TEXT,
    similarity FLOAT,
    fts_rank FLOAT,
    rrf_score FLOAT,
    search_type TEXT
)
LANGUAGE plpgsql
AS $$
DECLARE
    query_tsv tsquery;
BEGIN
    query_tsv := plainto_tsquery('english', query_text);

    RETURN QUERY
    WITH vector_results AS (
        SELECT
            e.embedding_id,
            e.data_id,
            e.chunk_text,
            1 - (e.embedding <=> query_embedding::vector) AS sim,
            ROW_NUMBER() OVER (ORDER BY e.embedding <=> query_embedding::vector) AS v_rank
        FROM mem_dog_embeddings e
        WHERE (filter_user_id IS NULL OR e.user_id = filter_user_id)
          AND (filter_data_ids IS NULL OR e.data_id = ANY(filter_data_ids))
        ORDER BY e.embedding <=> query_embedding::vector
        LIMIT match_count * 3
    ),
    fts_results AS (
        SELECT
            e.embedding_id,
            e.data_id,
            e.chunk_text,
            ts_rank_cd(e.chunk_tsv, query_tsv) AS fts_r,
            ROW_NUMBER() OVER (ORDER BY ts_rank_cd(e.chunk_tsv, query_tsv) DESC) AS f_rank
        FROM mem_dog_embeddings e
        WHERE e.chunk_tsv @@ query_tsv
          AND (filter_user_id IS NULL OR e.user_id = filter_user_id)
          AND (filter_data_ids IS NULL OR e.data_id = ANY(filter_data_ids))
        ORDER BY ts_rank_cd(e.chunk_tsv, query_tsv) DESC
        LIMIT match_count * 3
    ),
    combined AS (
        SELECT
            COALESCE(v.embedding_id, f.embedding_id) AS eid,
            COALESCE(v.data_id, f.data_id) AS did,
            COALESCE(v.chunk_text, f.chunk_text) AS ct,
            COALESCE(v.sim, 0.0) AS sim,
            COALESCE(f.fts_r, 0.0) AS fts_r,
            COALESCE(vector_weight / (rrf_k + COALESCE(v.v_rank, match_count * 3 + 1)), 0.0)
            + COALESCE(fts_weight / (rrf_k + COALESCE(f.f_rank, match_count * 3 + 1)), 0.0) AS rrf,
            CASE
                WHEN v.embedding_id IS NOT NULL AND f.embedding_id IS NOT NULL THEN 'both'
                WHEN v.embedding_id IS NOT NULL THEN 'vector'
                ELSE 'fts'
            END AS stype
        FROM vector_results v
        FULL OUTER JOIN fts_results f ON v.embedding_id = f.embedding_id
    )
    SELECT c.eid, c.did, c.ct, c.sim::FLOAT, c.fts_r::FLOAT, c.rrf::FLOAT, c.stype
    FROM combined c
    ORDER BY c.rrf DESC
    LIMIT match_count;
END;
$$;

-- 3. Pure full-text search RPC (no embedding needed)
CREATE OR REPLACE FUNCTION match_embeddings_fts(
    query_text TEXT,
    match_count INT DEFAULT 5,
    filter_user_id TEXT DEFAULT NULL,
    filter_data_ids TEXT[] DEFAULT NULL
)
RETURNS TABLE (
    embedding_id TEXT,
    data_id TEXT,
    chunk_text TEXT,
    fts_rank FLOAT
)
LANGUAGE plpgsql
AS $$
DECLARE
    query_tsv tsquery;
BEGIN
    query_tsv := plainto_tsquery('english', query_text);

    RETURN QUERY
    SELECT
        e.embedding_id,
        e.data_id,
        e.chunk_text,
        ts_rank_cd(e.chunk_tsv, query_tsv)::FLOAT AS fts_rank
    FROM mem_dog_embeddings e
    WHERE e.chunk_tsv @@ query_tsv
      AND (filter_user_id IS NULL OR e.user_id = filter_user_id)
      AND (filter_data_ids IS NULL OR e.data_id = ANY(filter_data_ids))
    ORDER BY ts_rank_cd(e.chunk_tsv, query_tsv) DESC
    LIMIT match_count;
END;
$$;
