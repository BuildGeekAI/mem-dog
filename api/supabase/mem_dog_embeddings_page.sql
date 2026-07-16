-- Phase 2: page / section metadata on embeddings for RAG citations.
-- Safe on base seed schema (02-mem-dog-embeddings) without organizations/FTS.
--
--   psql -U postgres -d postgres -f api/supabase/mem_dog_embeddings_page.sql
--
-- Prerequisites: mem_dog_embeddings table exists.
-- Optional: organizations.sql (project_id) and mem_dog_embeddings_fts.sql (chunk_tsv).
--   - match_embeddings always recreated with page return columns.
--   - hybrid/FTS RPCs updated only when chunk_tsv already exists.
-- DROP+CREATE for match_embeddings is atomic in one DO block (no grants
-- inside) so a missing Supabase role cannot leave search RPCs dropped.

ALTER TABLE mem_dog_embeddings
    ADD COLUMN IF NOT EXISTS page INT;

ALTER TABLE mem_dog_embeddings
    ADD COLUMN IF NOT EXISTS section_path TEXT[];

ALTER TABLE mem_dog_embeddings
    ADD COLUMN IF NOT EXISTS element_type TEXT;

ALTER TABLE mem_dog_embeddings
    ADD COLUMN IF NOT EXISTS embedding_kind TEXT;

-- Best-effort GRANT helper (Supabase roles may be absent in local Postgres).
CREATE OR REPLACE FUNCTION _md_grant_match_exec(fn_sig text)
RETURNS void
LANGUAGE plpgsql
AS $$
DECLARE
    role_name text;
BEGIN
    FOREACH role_name IN ARRAY ARRAY['service_role', 'anon', 'authenticated']
    LOOP
        BEGIN
            EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO %I', fn_sig, role_name);
        EXCEPTION
            WHEN undefined_object THEN
                RAISE NOTICE 'skip GRANT % TO % (role missing)', fn_sig, role_name;
            WHEN insufficient_privilege THEN
                RAISE NOTICE 'skip GRANT % TO % (insufficient privilege)', fn_sig, role_name;
        END;
    END LOOP;
END;
$$;

-- ---------------------------------------------------------------------------
-- match_embeddings: always recreate. Include project_id filter only when
-- the column exists (organizations.sql). Never reference project_id otherwise.
-- ---------------------------------------------------------------------------
DO $mig$
DECLARE
    has_project boolean;
BEGIN
    SELECT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'mem_dog_embeddings'
          AND column_name = 'project_id'
    ) INTO has_project;

    DROP FUNCTION IF EXISTS match_embeddings(TEXT, INT, TEXT, TEXT[], TEXT);
    DROP FUNCTION IF EXISTS match_embeddings(TEXT, INT, TEXT, TEXT[]);

    IF has_project THEN
        EXECUTE $fn$
            CREATE FUNCTION match_embeddings(
                query_embedding    TEXT,
                match_count        INT  DEFAULT 5,
                filter_user_id     TEXT DEFAULT NULL,
                filter_data_ids    TEXT[] DEFAULT NULL,
                filter_project_id  TEXT DEFAULT NULL
            )
            RETURNS TABLE (
                embedding_id TEXT,
                data_id      TEXT,
                chunk_text   TEXT,
                similarity   FLOAT,
                page         INT
            )
            LANGUAGE sql
            STABLE
            AS $body$
                SELECT
                    e.embedding_id,
                    e.data_id,
                    e.chunk_text,
                    1 - (e.vector <=> query_embedding::vector) AS similarity,
                    e.page
                FROM mem_dog_embeddings e
                WHERE e.vector IS NOT NULL
                  AND (filter_user_id IS NULL OR e.user_id = filter_user_id)
                  AND (filter_data_ids IS NULL OR e.data_id = ANY(filter_data_ids))
                  AND (filter_project_id IS NULL OR e.project_id = filter_project_id)
                ORDER BY e.vector <=> query_embedding::vector
                LIMIT match_count;
            $body$
        $fn$;
    ELSE
        EXECUTE $fn$
            CREATE FUNCTION match_embeddings(
                query_embedding  TEXT,
                match_count      INT  DEFAULT 5,
                filter_user_id   TEXT DEFAULT NULL,
                filter_data_ids  TEXT[] DEFAULT NULL
            )
            RETURNS TABLE (
                embedding_id TEXT,
                data_id      TEXT,
                chunk_text   TEXT,
                similarity   FLOAT,
                page         INT
            )
            LANGUAGE sql
            STABLE
            AS $body$
                SELECT
                    e.embedding_id,
                    e.data_id,
                    e.chunk_text,
                    1 - (e.vector <=> query_embedding::vector) AS similarity,
                    e.page
                FROM mem_dog_embeddings e
                WHERE e.vector IS NOT NULL
                  AND (filter_user_id IS NULL OR e.user_id = filter_user_id)
                  AND (filter_data_ids IS NULL OR e.data_id = ANY(filter_data_ids))
                ORDER BY e.vector <=> query_embedding::vector
                LIMIT match_count;
            $body$
        $fn$;
    END IF;
END
$mig$;

DO $grant$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'mem_dog_embeddings'
          AND column_name = 'project_id'
    ) THEN
        PERFORM _md_grant_match_exec('match_embeddings(TEXT, INT, TEXT, TEXT[], TEXT)');
    ELSE
        PERFORM _md_grant_match_exec('match_embeddings(TEXT, INT, TEXT, TEXT[])');
    END IF;
END
$grant$;

-- ---------------------------------------------------------------------------
-- Hybrid / FTS: only when chunk_tsv exists (mem_dog_embeddings_fts.sql).
-- Skip without DROPping — preserves older FTS RPCs or no-op when FTS absent.
-- ---------------------------------------------------------------------------
DO $mig$
DECLARE
    has_tsv boolean;
BEGIN
    SELECT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'mem_dog_embeddings'
          AND column_name = 'chunk_tsv'
    ) INTO has_tsv;

    IF NOT has_tsv THEN
        RAISE NOTICE
            'Skipping match_embeddings_hybrid/fts page update — chunk_tsv missing (apply mem_dog_embeddings_fts.sql first).';
        RETURN;
    END IF;

    DROP FUNCTION IF EXISTS match_embeddings_hybrid(TEXT, TEXT, INT, TEXT, TEXT[], FLOAT, FLOAT, INT);

    EXECUTE $fn$
        CREATE FUNCTION match_embeddings_hybrid(
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
            search_type TEXT,
            page INT
        )
        LANGUAGE plpgsql
        AS $body$
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
                    e.page AS page_num,
                    1 - (e.vector <=> query_embedding::vector) AS sim,
                    ROW_NUMBER() OVER (ORDER BY e.vector <=> query_embedding::vector) AS v_rank
                FROM mem_dog_embeddings e
                WHERE e.vector IS NOT NULL
                  AND (filter_user_id IS NULL OR e.user_id = filter_user_id)
                  AND (filter_data_ids IS NULL OR e.data_id = ANY(filter_data_ids))
                ORDER BY e.vector <=> query_embedding::vector
                LIMIT match_count * 3
            ),
            fts_results AS (
                SELECT
                    e.embedding_id,
                    e.data_id,
                    e.chunk_text,
                    e.page AS page_num,
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
                    COALESCE(v.page_num, f.page_num) AS pg,
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
            SELECT c.eid, c.did, c.ct, c.sim::FLOAT, c.fts_r::FLOAT, c.rrf::FLOAT, c.stype, c.pg
            FROM combined c
            ORDER BY c.rrf DESC
            LIMIT match_count;
        END;
        $body$
    $fn$;

    DROP FUNCTION IF EXISTS match_embeddings_fts(TEXT, INT, TEXT, TEXT[]);

    EXECUTE $fn$
        CREATE FUNCTION match_embeddings_fts(
            query_text TEXT,
            match_count INT DEFAULT 5,
            filter_user_id TEXT DEFAULT NULL,
            filter_data_ids TEXT[] DEFAULT NULL
        )
        RETURNS TABLE (
            embedding_id TEXT,
            data_id TEXT,
            chunk_text TEXT,
            fts_rank FLOAT,
            page INT
        )
        LANGUAGE plpgsql
        AS $body$
        DECLARE
            query_tsv tsquery;
        BEGIN
            query_tsv := plainto_tsquery('english', query_text);

            RETURN QUERY
            SELECT
                e.embedding_id,
                e.data_id,
                e.chunk_text,
                ts_rank_cd(e.chunk_tsv, query_tsv)::FLOAT AS fts_rank,
                e.page
            FROM mem_dog_embeddings e
            WHERE e.chunk_tsv @@ query_tsv
              AND (filter_user_id IS NULL OR e.user_id = filter_user_id)
              AND (filter_data_ids IS NULL OR e.data_id = ANY(filter_data_ids))
            ORDER BY ts_rank_cd(e.chunk_tsv, query_tsv) DESC
            LIMIT match_count;
        END;
        $body$
    $fn$;

    PERFORM _md_grant_match_exec('match_embeddings_hybrid(TEXT, TEXT, INT, TEXT, TEXT[], FLOAT, FLOAT, INT)');
    PERFORM _md_grant_match_exec('match_embeddings_fts(TEXT, INT, TEXT, TEXT[])');
END
$mig$;

DROP FUNCTION IF EXISTS _md_grant_match_exec(text);

NOTIFY pgrst, 'reload schema';
