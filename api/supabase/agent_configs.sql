CREATE TABLE IF NOT EXISTS agent_configs (
    config_id     TEXT        PRIMARY KEY,
    agent_type    TEXT        NOT NULL,
    user_id       TEXT,                        -- NULL = system default
    intro         TEXT,
    system_prompt TEXT,
    output_schema TEXT,
    skills        JSONB       NOT NULL DEFAULT '[]',
    model_tier    TEXT,
    parameters    JSONB       NOT NULL DEFAULT '{}',
    version       INTEGER     NOT NULL DEFAULT 1,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (agent_type, user_id)
);

CREATE INDEX ON agent_configs (agent_type, user_id);

GRANT ALL ON public.agent_configs TO service_role, anon, authenticated;
NOTIFY pgrst, 'reload schema';
