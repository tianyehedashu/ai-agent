-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260508_add_gateway_tables.py
-- revision: 20260508_gw
-- down_revision: 20260508_pc
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

CREATE TABLE gateway_teams (
    id UUID NOT NULL, 
    name VARCHAR(100) NOT NULL, 
    slug VARCHAR(100) NOT NULL, 
    kind VARCHAR(20) DEFAULT 'shared' NOT NULL, 
    owner_user_id UUID NOT NULL, 
    settings JSONB, 
    is_active BOOLEAN DEFAULT 'true' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_gateway_teams_owner_slug UNIQUE (owner_user_id, slug), 
    FOREIGN KEY(owner_user_id) REFERENCES users (id) ON DELETE CASCADE
);
CREATE INDEX ix_gateway_teams_slug ON gateway_teams (slug);
CREATE INDEX ix_gateway_teams_owner ON gateway_teams (owner_user_id);
CREATE TABLE gateway_team_members (
    id UUID NOT NULL, 
    team_id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    role VARCHAR(20) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_gateway_team_members UNIQUE (team_id, user_id), 
    FOREIGN KEY(team_id) REFERENCES gateway_teams (id) ON DELETE CASCADE, 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);
CREATE INDEX ix_gateway_team_members_team ON gateway_team_members (team_id);
CREATE INDEX ix_gateway_team_members_user ON gateway_team_members (user_id);
WITH new_teams AS (
            INSERT INTO gateway_teams (
                id, name, slug, kind, owner_user_id, is_active,
                created_at, updated_at
            )
            SELECT
                gen_random_uuid(),
                COALESCE(u.name, split_part(u.email, '@', 1), 'Personal'),
                'personal-' || u.id::text,
                'personal',
                u.id,
                true,
                COALESCE(u.created_at, now()),
                now()
            FROM users u
            WHERE NOT EXISTS (
                SELECT 1 FROM gateway_teams gt
                WHERE gt.owner_user_id = u.id AND gt.kind = 'personal'
            )
            RETURNING id, owner_user_id
        )
        INSERT INTO gateway_team_members (
            id, team_id, user_id, role, created_at, updated_at
        )
        SELECT gen_random_uuid(), nt.id, nt.owner_user_id, 'owner', now(), now()
        FROM new_teams nt;
CREATE TABLE gateway_virtual_keys (
    id UUID NOT NULL, 
    team_id UUID NOT NULL, 
    created_by_user_id UUID, 
    name VARCHAR(100) NOT NULL, 
    description TEXT, 
    key_prefix VARCHAR(16) DEFAULT 'sk-gw-' NOT NULL, 
    key_id VARCHAR(16) NOT NULL, 
    key_hash VARCHAR(255) NOT NULL, 
    encrypted_key VARCHAR(512) NOT NULL, 
    allowed_models VARCHAR(200)[] DEFAULT '{}' NOT NULL, 
    allowed_capabilities VARCHAR(40)[] DEFAULT '{}' NOT NULL, 
    rpm_limit INTEGER, 
    tpm_limit INTEGER, 
    store_full_messages BOOLEAN DEFAULT 'false' NOT NULL, 
    guardrail_enabled BOOLEAN DEFAULT 'true' NOT NULL, 
    is_system BOOLEAN DEFAULT 'false' NOT NULL, 
    is_active BOOLEAN DEFAULT 'true' NOT NULL, 
    expires_at TIMESTAMP WITH TIME ZONE, 
    last_used_at TIMESTAMP WITH TIME ZONE, 
    usage_count INTEGER DEFAULT '0' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(team_id) REFERENCES gateway_teams (id) ON DELETE CASCADE, 
    FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
    UNIQUE (key_hash)
);
CREATE INDEX ix_gateway_virtual_keys_team ON gateway_virtual_keys (team_id);
CREATE INDEX ix_gateway_virtual_keys_user ON gateway_virtual_keys (created_by_user_id);
CREATE INDEX ix_gateway_virtual_keys_key_id ON gateway_virtual_keys (key_id);
CREATE INDEX ix_gateway_virtual_keys_active ON gateway_virtual_keys (is_active);
CREATE INDEX ix_gateway_virtual_keys_system ON gateway_virtual_keys (is_system);
CREATE INDEX ix_gateway_virtual_keys_expires ON gateway_virtual_keys (expires_at);
CREATE TABLE gateway_models (
    id UUID NOT NULL, 
    team_id UUID, 
    name VARCHAR(200) NOT NULL, 
    capability VARCHAR(40) NOT NULL, 
    real_model VARCHAR(200) NOT NULL, 
    credential_id UUID NOT NULL, 
    provider VARCHAR(50) NOT NULL, 
    weight INTEGER DEFAULT '1' NOT NULL, 
    rpm_limit INTEGER, 
    tpm_limit INTEGER, 
    enabled BOOLEAN DEFAULT 'true' NOT NULL, 
    tags JSONB, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_gateway_models_team_name UNIQUE (team_id, name), 
    FOREIGN KEY(team_id) REFERENCES gateway_teams (id) ON DELETE CASCADE, 
    FOREIGN KEY(credential_id) REFERENCES provider_credentials (id) ON DELETE RESTRICT
);
CREATE INDEX ix_gateway_models_team ON gateway_models (team_id);
CREATE INDEX ix_gateway_models_capability ON gateway_models (capability);
CREATE INDEX ix_gateway_models_credential ON gateway_models (credential_id);
CREATE INDEX ix_gateway_models_provider ON gateway_models (provider);
CREATE INDEX ix_gateway_models_lookup ON gateway_models (team_id, capability, enabled);
CREATE TABLE gateway_routes (
    id UUID NOT NULL, 
    team_id UUID, 
    virtual_model VARCHAR(200) NOT NULL, 
    primary_models VARCHAR(200)[] DEFAULT '{}' NOT NULL, 
    fallbacks_general VARCHAR(200)[] DEFAULT '{}' NOT NULL, 
    fallbacks_content_policy VARCHAR(200)[] DEFAULT '{}' NOT NULL, 
    fallbacks_context_window VARCHAR(200)[] DEFAULT '{}' NOT NULL, 
    strategy VARCHAR(40) DEFAULT 'simple-shuffle' NOT NULL, 
    retry_policy JSONB, 
    enabled BOOLEAN DEFAULT 'true' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_gateway_routes_team_virtual_model UNIQUE (team_id, virtual_model), 
    FOREIGN KEY(team_id) REFERENCES gateway_teams (id) ON DELETE CASCADE
);
CREATE INDEX ix_gateway_routes_team ON gateway_routes (team_id);
CREATE INDEX ix_gateway_routes_vmodel ON gateway_routes (virtual_model);
CREATE TABLE gateway_budgets (
    id UUID NOT NULL, 
    scope VARCHAR(20) NOT NULL, 
    scope_id UUID, 
    period VARCHAR(20) NOT NULL, 
    limit_usd NUMERIC(12, 4), 
    limit_tokens INTEGER, 
    limit_requests INTEGER, 
    current_usd NUMERIC(12, 4) DEFAULT '0' NOT NULL, 
    current_tokens INTEGER DEFAULT '0' NOT NULL, 
    current_requests INTEGER DEFAULT '0' NOT NULL, 
    reset_at TIMESTAMP WITH TIME ZONE, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_gateway_budgets_scope_period UNIQUE (scope, scope_id, period)
);
CREATE INDEX ix_gateway_budgets_scope ON gateway_budgets (scope);
CREATE INDEX ix_gateway_budgets_scope_id ON gateway_budgets (scope_id);
CREATE INDEX ix_gateway_budgets_lookup ON gateway_budgets (scope, scope_id);
CREATE TABLE gateway_request_logs (
            id UUID NOT NULL DEFAULT gen_random_uuid(),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            team_id UUID NULL,
            user_id UUID NULL,
            vkey_id UUID NULL,
            team_snapshot JSONB NULL,
            user_email_snapshot VARCHAR(255) NULL,
            vkey_name_snapshot VARCHAR(100) NULL,
            route_snapshot JSONB NULL,
            capability VARCHAR(40) NOT NULL,
            route_name VARCHAR(200) NULL,
            real_model VARCHAR(200) NULL,
            provider VARCHAR(50) NULL,
            status VARCHAR(40) NOT NULL,
            error_code VARCHAR(100) NULL,
            error_message TEXT NULL,
            input_tokens INTEGER NOT NULL DEFAULT 0,
            output_tokens INTEGER NOT NULL DEFAULT 0,
            cached_tokens INTEGER NOT NULL DEFAULT 0,
            cost_usd NUMERIC(12, 6) NOT NULL DEFAULT 0,
            latency_ms INTEGER NOT NULL DEFAULT 0,
            ttfb_ms INTEGER NULL,
            cache_hit BOOLEAN NOT NULL DEFAULT false,
            fallback_chain VARCHAR(200)[] NOT NULL DEFAULT '{}',
            request_id VARCHAR(64) NULL,
            prompt_hash VARCHAR(64) NULL,
            prompt_redacted JSONB NULL,
            response_summary JSONB NULL,
            metadata_extra JSONB NULL,
            PRIMARY KEY (id, created_at)
        ) PARTITION BY RANGE (created_at);
CREATE INDEX ix_gateway_request_logs_team_time ON gateway_request_logs (team_id, created_at);
CREATE INDEX ix_gateway_request_logs_user_time ON gateway_request_logs (user_id, created_at);
CREATE INDEX ix_gateway_request_logs_vkey_time ON gateway_request_logs (vkey_id, created_at);
CREATE INDEX ix_gateway_request_logs_status_time ON gateway_request_logs (status, created_at);
CREATE INDEX ix_gateway_request_logs_capability ON gateway_request_logs (capability);
CREATE INDEX ix_gateway_request_logs_request_id ON gateway_request_logs (request_id);
CREATE TABLE IF NOT EXISTS gateway_request_logs_y2026m03
        PARTITION OF gateway_request_logs
        FOR VALUES FROM ('2026-03-01T00:00:00+00:00') TO ('2026-04-01T00:00:00+00:00');
CREATE TABLE IF NOT EXISTS gateway_request_logs_y2026m05
        PARTITION OF gateway_request_logs
        FOR VALUES FROM ('2026-05-01T00:00:00+00:00') TO ('2026-06-01T00:00:00+00:00');
CREATE TABLE IF NOT EXISTS gateway_request_logs_y2026m06
        PARTITION OF gateway_request_logs
        FOR VALUES FROM ('2026-06-01T00:00:00+00:00') TO ('2026-07-01T00:00:00+00:00');
CREATE TABLE IF NOT EXISTS gateway_request_logs_y2026m07
        PARTITION OF gateway_request_logs
        FOR VALUES FROM ('2026-07-01T00:00:00+00:00') TO ('2026-08-01T00:00:00+00:00');
CREATE TABLE gateway_metrics_hourly (
    id UUID NOT NULL, 
    bucket_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    team_id UUID, 
    user_id UUID, 
    vkey_id UUID, 
    provider VARCHAR(50), 
    real_model VARCHAR(200), 
    capability VARCHAR(40), 
    requests INTEGER DEFAULT '0' NOT NULL, 
    success_count INTEGER DEFAULT '0' NOT NULL, 
    error_count INTEGER DEFAULT '0' NOT NULL, 
    input_tokens INTEGER DEFAULT '0' NOT NULL, 
    output_tokens INTEGER DEFAULT '0' NOT NULL, 
    cached_tokens INTEGER DEFAULT '0' NOT NULL, 
    cost_usd NUMERIC(14, 6) DEFAULT '0' NOT NULL, 
    total_latency_ms INTEGER DEFAULT '0' NOT NULL, 
    p95_latency_ms INTEGER DEFAULT '0' NOT NULL, 
    cache_hit_count INTEGER DEFAULT '0' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_gateway_metrics_hourly_dim UNIQUE (bucket_at, team_id, user_id, vkey_id, provider, real_model, capability)
);
CREATE INDEX ix_gateway_metrics_hourly_bucket ON gateway_metrics_hourly (bucket_at);
CREATE INDEX ix_gateway_metrics_hourly_team_bucket ON gateway_metrics_hourly (team_id, bucket_at);
CREATE TABLE gateway_alert_rules (
    id UUID NOT NULL, 
    team_id UUID, 
    name VARCHAR(100) NOT NULL, 
    description TEXT, 
    metric VARCHAR(40) NOT NULL, 
    threshold NUMERIC(12, 4) NOT NULL, 
    window_minutes INTEGER DEFAULT '5' NOT NULL, 
    channels JSONB DEFAULT '{}' NOT NULL, 
    enabled BOOLEAN DEFAULT 'true' NOT NULL, 
    last_triggered_at TIMESTAMP WITH TIME ZONE, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(team_id) REFERENCES gateway_teams (id) ON DELETE CASCADE
);
CREATE INDEX ix_gateway_alert_rules_team ON gateway_alert_rules (team_id);
CREATE INDEX ix_gateway_alert_rules_lookup ON gateway_alert_rules (team_id, enabled);
CREATE TABLE gateway_alert_events (
    id UUID NOT NULL, 
    rule_id UUID NOT NULL, 
    team_id UUID, 
    metric_value NUMERIC(12, 4) NOT NULL, 
    threshold NUMERIC(12, 4) NOT NULL, 
    severity VARCHAR(20) DEFAULT 'warning' NOT NULL, 
    payload JSONB, 
    notified BOOLEAN DEFAULT 'false' NOT NULL, 
    acknowledged BOOLEAN DEFAULT 'false' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(rule_id) REFERENCES gateway_alert_rules (id) ON DELETE CASCADE
);
CREATE INDEX ix_gateway_alert_events_rule ON gateway_alert_events (rule_id);
CREATE INDEX ix_gateway_alert_events_team ON gateway_alert_events (team_id);
