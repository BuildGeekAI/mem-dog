-- Per-user API keys table for O(1) validation via key_hash index.
-- Run in Supabase SQL Editor after profiles table exists.

CREATE TABLE IF NOT EXISTS api_keys (
    key_id      TEXT        PRIMARY KEY,
    user_id     TEXT        NOT NULL REFERENCES profiles(user_id) ON DELETE CASCADE,
    key_hash    TEXT        NOT NULL UNIQUE,
    name        TEXT        NOT NULL,
    expires_at  TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_api_keys_key_hash ON api_keys (key_hash);
CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON api_keys (user_id);
