-- organizations: org/project hierarchy for multi-tenant scoping.
--
-- Three tables: organizations, projects, org_members.
-- Plus ALTER TABLE statements to add org_id/project_id to existing tables.
--
-- Run in Supabase SQL Editor or via psql.

-- ---------------------------------------------------------------------------
-- Table: organizations
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS organizations (
    org_id         TEXT        PRIMARY KEY,
    name           TEXT        NOT NULL UNIQUE,
    display_name   TEXT,
    owner_user_id  TEXT        NOT NULL,
    metadata       JSONB       NOT NULL DEFAULT '{}',
    status         TEXT        NOT NULL DEFAULT 'active',
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Table: projects
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS projects (
    project_id     TEXT        PRIMARY KEY,
    org_id         TEXT        NOT NULL REFERENCES organizations(org_id) ON DELETE CASCADE,
    name           TEXT        NOT NULL,
    display_name   TEXT,
    description    TEXT,
    metadata       JSONB       NOT NULL DEFAULT '{}',
    status         TEXT        NOT NULL DEFAULT 'active',
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (org_id, name)
);

CREATE INDEX IF NOT EXISTS projects_org_idx ON projects (org_id);

-- ---------------------------------------------------------------------------
-- Table: org_members
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS org_members (
    org_id         TEXT        NOT NULL REFERENCES organizations(org_id) ON DELETE CASCADE,
    user_id        TEXT        NOT NULL,
    role           TEXT        NOT NULL DEFAULT 'member',
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (org_id, user_id)
);

CREATE INDEX IF NOT EXISTS org_members_user_idx ON org_members (user_id);

-- ---------------------------------------------------------------------------
-- Alter existing tables: add nullable org_id/project_id columns
-- ---------------------------------------------------------------------------

-- mem_dog_blobs
ALTER TABLE mem_dog_blobs ADD COLUMN IF NOT EXISTS org_id TEXT;
ALTER TABLE mem_dog_blobs ADD COLUMN IF NOT EXISTS project_id TEXT;
CREATE INDEX IF NOT EXISTS mem_dog_blobs_project_idx ON mem_dog_blobs (project_id) WHERE project_id IS NOT NULL;

-- mem_dog_embeddings
ALTER TABLE mem_dog_embeddings ADD COLUMN IF NOT EXISTS org_id TEXT;
ALTER TABLE mem_dog_embeddings ADD COLUMN IF NOT EXISTS project_id TEXT;
CREATE INDEX IF NOT EXISTS mem_dog_embeddings_project_idx ON mem_dog_embeddings (project_id) WHERE project_id IS NOT NULL;

-- profiles
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS default_org_id TEXT;
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS default_project_id TEXT;

-- ---------------------------------------------------------------------------
-- Update list_data_paginated RPC to support project_id filter
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION list_data_paginated(
    p_user_id    TEXT DEFAULT NULL,
    p_skip       INT  DEFAULT 0,
    p_limit      INT  DEFAULT 50,
    p_tags       TEXT[] DEFAULT NULL,
    p_match_all  BOOLEAN DEFAULT FALSE,
    p_project_id TEXT DEFAULT NULL
)
RETURNS TABLE (path TEXT, content TEXT, total BIGINT)
LANGUAGE sql
STABLE
AS $$
  WITH decoded AS (
    SELECT
      b.path,
      b.content,
      convert_from(decode(b.content, 'base64'), 'UTF8')::jsonb AS j
    FROM mem_dog_blobs b
    WHERE b.store_name = 'meta'
      AND (p_user_id IS NULL OR b.path LIKE p_user_id || '/%')
      AND b.path LIKE '%/meta.json'
      AND b.path NOT LIKE '%/ver_%'
      AND (p_project_id IS NULL OR b.project_id = p_project_id)
  ),
  filtered AS (
    SELECT
      d.path,
      d.content,
      d.j,
      COUNT(*) OVER () AS total
    FROM decoded d
    WHERE (
      p_tags IS NULL
      OR array_length(p_tags, 1) IS NULL
      OR (
        CASE
          WHEN p_match_all THEN (d.j -> 'tags') @> to_jsonb(p_tags)
          ELSE (d.j -> 'tags') ?| p_tags
        END
      )
    )
  )
  SELECT f.path, f.content, f.total
  FROM filtered f
  ORDER BY (f.j ->> 'updated_at') DESC NULLS LAST
  LIMIT p_limit
  OFFSET p_skip;
$$;

-- Grant execute to PostgREST roles (overwrite old signature)
DROP FUNCTION IF EXISTS list_data_paginated(TEXT, INT, INT, TEXT[], BOOLEAN);
GRANT EXECUTE ON FUNCTION list_data_paginated(TEXT, INT, INT, TEXT[], BOOLEAN, TEXT) TO service_role;
GRANT EXECUTE ON FUNCTION list_data_paginated(TEXT, INT, INT, TEXT[], BOOLEAN, TEXT) TO anon;
GRANT EXECUTE ON FUNCTION list_data_paginated(TEXT, INT, INT, TEXT[], BOOLEAN, TEXT) TO authenticated;

-- ---------------------------------------------------------------------------
-- Update match_embeddings RPC to support project_id filter
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION match_embeddings(
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
      AND (filter_project_id IS NULL OR e.project_id = filter_project_id)
    ORDER BY e.vector <=> query_embedding::vector
    LIMIT match_count;
$$;

-- Grant execute (overwrite old signature)
DROP FUNCTION IF EXISTS match_embeddings(TEXT, INT, TEXT, TEXT[]);
GRANT EXECUTE ON FUNCTION match_embeddings(TEXT, INT, TEXT, TEXT[], TEXT) TO service_role;
GRANT EXECUTE ON FUNCTION match_embeddings(TEXT, INT, TEXT, TEXT[], TEXT) TO anon;
GRANT EXECUTE ON FUNCTION match_embeddings(TEXT, INT, TEXT, TEXT[], TEXT) TO authenticated;

-- ---------------------------------------------------------------------------
-- Grants for new tables
-- ---------------------------------------------------------------------------

GRANT ALL ON public.organizations TO service_role;
GRANT ALL ON public.organizations TO anon;
GRANT ALL ON public.organizations TO authenticated;

GRANT ALL ON public.projects TO service_role;
GRANT ALL ON public.projects TO anon;
GRANT ALL ON public.projects TO authenticated;

GRANT ALL ON public.org_members TO service_role;
GRANT ALL ON public.org_members TO anon;
GRANT ALL ON public.org_members TO authenticated;

-- ---------------------------------------------------------------------------
-- Reload PostgREST schema cache
-- ---------------------------------------------------------------------------

NOTIFY pgrst, 'reload schema';
