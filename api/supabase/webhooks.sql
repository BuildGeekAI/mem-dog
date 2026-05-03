-- Per-user webhook endpoints with unique IDs.
-- Each webhook maps to exactly one user and channel type.
-- External services POST to /webhooks/{webhook_id} instead of /webhooks/{channel_type}.

CREATE TABLE IF NOT EXISTS webhooks (
    webhook_id      TEXT        PRIMARY KEY,
    user_id         TEXT        NOT NULL REFERENCES profiles(user_id) ON DELETE CASCADE,
    channel_type    TEXT        NOT NULL,
    name            TEXT        NOT NULL DEFAULT '',
    secret_hash     TEXT,
    status          TEXT        NOT NULL DEFAULT 'active',
    config          JSONB       NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_webhooks_user_id ON webhooks (user_id);
CREATE INDEX IF NOT EXISTS idx_webhooks_status ON webhooks (status) WHERE status = 'active';

-- Event log for per-webhook observability.
-- Every inbound hit is recorded with status and error detail.

CREATE TABLE IF NOT EXISTS webhook_events (
    event_id        TEXT        PRIMARY KEY,
    webhook_id      TEXT        NOT NULL REFERENCES webhooks(webhook_id) ON DELETE CASCADE,
    user_id         TEXT        NOT NULL,
    channel_type    TEXT        NOT NULL,
    status          TEXT        NOT NULL,
    error_message   TEXT,
    error_stage     TEXT,
    payload_bytes   INTEGER,
    latency_ms      INTEGER,
    trace_id        TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_webhook_events_webhook_id ON webhook_events (webhook_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_webhook_events_user_id ON webhook_events (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_webhook_events_status ON webhook_events (status, created_at DESC);
