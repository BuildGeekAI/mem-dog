-- profiles table: dedicated Supabase table for user profiles
-- Replaces the blob-based users/{user_id}/profile.json pattern

CREATE TABLE IF NOT EXISTS profiles (
    user_id            TEXT        PRIMARY KEY,
    username           TEXT        NOT NULL UNIQUE,
    email              TEXT        NOT NULL DEFAULT '',
    display_name       TEXT,
    role               TEXT        NOT NULL DEFAULT 'user',
    status             TEXT        NOT NULL DEFAULT 'active',
    metadata           JSONB       NOT NULL DEFAULT '{}',
    data_count         INTEGER     NOT NULL DEFAULT 0,
    storage_used_bytes BIGINT      NOT NULL DEFAULT 0,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_active_at     TIMESTAMPTZ
);

-- Seed demo user
INSERT INTO profiles (user_id, username, email, display_name)
VALUES ('00000000-0000-0000-0000-000000000001', 'demo', 'demo@localhost', 'Demo')
ON CONFLICT (user_id) DO NOTHING;
