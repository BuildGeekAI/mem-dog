-- list_data_paginated: RPC for paginated data list with optional tag filter.
--
-- Used when STORAGE_BACKEND=supabase to push pagination and tag filtering
-- into the database instead of loading all meta blobs. Run after mem_dog_blobs.sql.
--
-- Run in Supabase SQL Editor or via psql.

-- ---------------------------------------------------------------------------
-- Function: list_data_paginated
-- Returns: (path, content, total) for the current page. content is base64.
-- ---------------------------------------------------------------------------

-- Content in mem_dog_blobs is stored base64-encoded; decode for JSON ops.
CREATE OR REPLACE FUNCTION list_data_paginated(
    p_user_id   TEXT DEFAULT NULL,
    p_skip      INT  DEFAULT 0,
    p_limit     INT  DEFAULT 50,
    p_tags      TEXT[] DEFAULT NULL,
    p_match_all BOOLEAN DEFAULT FALSE
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

-- Grant execute to PostgREST roles
GRANT EXECUTE ON FUNCTION list_data_paginated(TEXT, INT, INT, TEXT[], BOOLEAN) TO service_role;
GRANT EXECUTE ON FUNCTION list_data_paginated(TEXT, INT, INT, TEXT[], BOOLEAN) TO anon;
GRANT EXECUTE ON FUNCTION list_data_paginated(TEXT, INT, INT, TEXT[], BOOLEAN) TO authenticated;

NOTIFY pgrst, 'reload schema';
