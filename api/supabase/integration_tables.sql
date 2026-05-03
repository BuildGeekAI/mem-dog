-- =============================================================================
-- Integration Platform tables (Nango-like provider + connection management)
-- =============================================================================
-- Run this in the Supabase SQL Editor to create the integration tables.

-- ---------------------------------------------------------------------------
-- 1. integration_providers — Provider catalog (100+ entries)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS integration_providers (
    provider_key      TEXT        PRIMARY KEY,
    display_name      TEXT        NOT NULL,
    description       TEXT        NOT NULL DEFAULT '',
    logo_url          TEXT        NOT NULL DEFAULT '',
    category          TEXT        NOT NULL DEFAULT 'other',
    auth_mode         TEXT        NOT NULL DEFAULT 'OAUTH2',   -- OAUTH2, API_KEY, BASIC, NONE
    authorization_url TEXT        NOT NULL DEFAULT '',
    token_url         TEXT        NOT NULL DEFAULT '',
    scope             TEXT        NOT NULL DEFAULT '',
    proxy_base_url    TEXT        NOT NULL DEFAULT '',
    config            JSONB       NOT NULL DEFAULT '{}',
    client_id_enc     TEXT        NOT NULL DEFAULT '',   -- Fernet-encrypted OAuth client_id
    client_secret_enc TEXT        NOT NULL DEFAULT '',   -- Fernet-encrypted OAuth client_secret
    is_enabled        BOOLEAN     NOT NULL DEFAULT true,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS integration_providers_category_idx
    ON integration_providers (category);

-- ---------------------------------------------------------------------------
-- 2. integration_connections — User-provider links
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS integration_connections (
    connection_id     TEXT        PRIMARY KEY,
    user_id           TEXT        NOT NULL,
    provider_key      TEXT        NOT NULL REFERENCES integration_providers(provider_key) ON DELETE CASCADE,
    display_name      TEXT        NOT NULL DEFAULT '',
    account_id        TEXT        NOT NULL DEFAULT '',
    account_email     TEXT        NOT NULL DEFAULT '',
    status            TEXT        NOT NULL DEFAULT 'active',    -- active, expired, revoked, error
    status_message    TEXT        NOT NULL DEFAULT '',
    scopes            TEXT        NOT NULL DEFAULT '',
    metadata          JSONB       NOT NULL DEFAULT '{}',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS integration_connections_user_idx
    ON integration_connections (user_id);
CREATE INDEX IF NOT EXISTS integration_connections_provider_idx
    ON integration_connections (provider_key);
CREATE UNIQUE INDEX IF NOT EXISTS integration_connections_unique_idx
    ON integration_connections (user_id, provider_key, account_id);

-- ---------------------------------------------------------------------------
-- 3. integration_credentials — Encrypted tokens (Fernet AES-256)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS integration_credentials (
    connection_id        TEXT        PRIMARY KEY REFERENCES integration_connections(connection_id) ON DELETE CASCADE,
    access_token_enc     TEXT        NOT NULL DEFAULT '',
    refresh_token_enc    TEXT        NOT NULL DEFAULT '',
    api_key_enc          TEXT        NOT NULL DEFAULT '',
    token_type           TEXT        NOT NULL DEFAULT 'bearer',
    expires_at           TIMESTAMPTZ,
    raw_token_response   TEXT        NOT NULL DEFAULT '',
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Grants
-- ---------------------------------------------------------------------------
GRANT ALL ON public.integration_providers   TO service_role;
GRANT ALL ON public.integration_connections TO service_role;
GRANT ALL ON public.integration_credentials TO service_role;
