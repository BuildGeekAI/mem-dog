-- mem_dog_blobs: general-purpose JSON blob store for all non-raw, non-embedding data.
--
-- Used by STORAGE_BACKEND=supabase as a drop-in replacement for GCS buckets
-- (meta, memories, viewpoints, users, prompts, skills, stats, channels, index,
-- ai_config).  Each logical store is a distinct `store_name` value; `path` is
-- the same relative blob path that would be used inside a GCS bucket.
--
-- Run this in Supabase SQL Editor (Dashboard → SQL Editor) or via:
--   kubectl exec -n supabase supabase-supabase-db-0 -c supabase-db -- \
--     psql -U postgres -d postgres -f /path/to/mem_dog_blobs.sql

-- ---------------------------------------------------------------------------
-- Table
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS mem_dog_blobs (
    store_name   TEXT        NOT NULL,
    path         TEXT        NOT NULL,
    -- Explicit tenant column for per-user queries and future Row Level Security.
    -- NULL for system-level stores (stats, channels, prompts, skills, ai_config).
    user_id      TEXT,
    -- base64-encoded blob content (JSON for most stores, arbitrary bytes possible).
    content      TEXT        NOT NULL,
    content_type TEXT        NOT NULL DEFAULT 'application/octet-stream',
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (store_name, path)
    -- ^ B-tree PK covers exact-path lookups: read, exists, delete, get_content_type.
);

-- ---------------------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------------------

-- Prefix scan index: required for list_blobs(prefix) which generates
--   WHERE store_name = ? AND path LIKE 'prefix%'
-- text_pattern_ops is needed because Supabase's default collation is not C;
-- without it, LIKE prefix% cannot use the B-tree index efficiently.
CREATE INDEX IF NOT EXISTS mem_dog_blobs_prefix_idx
    ON mem_dog_blobs (store_name, path text_pattern_ops);

-- User-scoped listing: WHERE store_name = ? AND user_id = ?
-- Also referenced by Row Level Security policies (disabled by default; see below).
CREATE INDEX IF NOT EXISTS mem_dog_blobs_user_idx
    ON mem_dog_blobs (store_name, user_id);

-- ---------------------------------------------------------------------------
-- Grants (PostgREST roles used by Supabase)
-- ---------------------------------------------------------------------------

GRANT ALL ON public.mem_dog_blobs TO service_role;
GRANT ALL ON public.mem_dog_blobs TO anon;
GRANT ALL ON public.mem_dog_blobs TO authenticated;

-- ---------------------------------------------------------------------------
-- Row Level Security (disabled by default)
--
-- The backend API uses the service_role key which bypasses RLS.  Enable these
-- policies when direct-client access with per-tenant isolation is required.
-- ---------------------------------------------------------------------------

-- ALTER TABLE mem_dog_blobs ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY user_isolation ON mem_dog_blobs
--     USING (user_id IS NULL OR user_id = current_setting('app.current_user_id', true));

-- ---------------------------------------------------------------------------
-- Reload PostgREST schema cache so the table is immediately accessible via REST.
-- ---------------------------------------------------------------------------

NOTIFY pgrst, 'reload schema';
