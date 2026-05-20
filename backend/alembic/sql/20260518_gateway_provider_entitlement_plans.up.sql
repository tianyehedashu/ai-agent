-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260518_gateway_provider_entitlement_plans.py
-- revision: 20260518_gpep
-- down_revision: 20260515_drop_pc_lum
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

CREATE TABLE provider_plans (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    credential_id UUID NOT NULL, 
    real_model VARCHAR(200), 
    label VARCHAR(100) NOT NULL, 
    valid_from TIMESTAMP WITH TIME ZONE NOT NULL, 
    valid_until TIMESTAMP WITH TIME ZONE NOT NULL, 
    is_active BOOLEAN DEFAULT true NOT NULL, 
    auto_renew BOOLEAN DEFAULT false NOT NULL, 
    notes TEXT, 
    extra JSONB, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(credential_id) REFERENCES provider_credentials (id) ON DELETE CASCADE
);
CREATE INDEX ix_provider_plans_credential_id ON provider_plans (credential_id);
CREATE INDEX ix_provider_plans_active ON provider_plans (credential_id, real_model, is_active, valid_from, valid_until);
CREATE TABLE provider_plan_quotas (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    plan_id UUID NOT NULL, 
    label VARCHAR(40) NOT NULL, 
    window_seconds INTEGER NOT NULL, 
    reset_strategy VARCHAR(32) DEFAULT 'rolling' NOT NULL, 
    limit_usd NUMERIC(12, 4), 
    limit_tokens INTEGER, 
    limit_requests INTEGER, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_provider_plan_quota_label UNIQUE (plan_id, label), 
    FOREIGN KEY(plan_id) REFERENCES provider_plans (id) ON DELETE CASCADE
);
CREATE INDEX ix_provider_plan_quotas_plan_id ON provider_plan_quotas (plan_id);
CREATE TABLE entitlement_plans (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    scope VARCHAR(20) NOT NULL, 
    scope_id UUID NOT NULL, 
    label VARCHAR(100) NOT NULL, 
    included_models VARCHAR(200)[] DEFAULT '{}'::character varying[] NOT NULL, 
    included_capabilities VARCHAR(40)[] DEFAULT '{}'::character varying[] NOT NULL, 
    valid_from TIMESTAMP WITH TIME ZONE NOT NULL, 
    valid_until TIMESTAMP WITH TIME ZONE NOT NULL, 
    is_active BOOLEAN DEFAULT true NOT NULL, 
    auto_renew BOOLEAN DEFAULT false NOT NULL, 
    notes TEXT, 
    extra JSONB, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id)
);
CREATE INDEX ix_entitlement_plans_scope_id ON entitlement_plans (scope_id);
CREATE INDEX ix_entitlement_plans_active ON entitlement_plans (scope, scope_id, is_active, valid_from, valid_until);
CREATE TABLE entitlement_plan_quotas (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    plan_id UUID NOT NULL, 
    label VARCHAR(40) NOT NULL, 
    window_seconds INTEGER NOT NULL, 
    reset_strategy VARCHAR(32) DEFAULT 'rolling' NOT NULL, 
    limit_usd NUMERIC(12, 4), 
    limit_tokens INTEGER, 
    limit_requests INTEGER, 
    unit_price_usd_per_token NUMERIC(12, 8), 
    unit_price_usd_per_request NUMERIC(12, 6), 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_entitlement_plan_quota_label UNIQUE (plan_id, label), 
    FOREIGN KEY(plan_id) REFERENCES entitlement_plans (id) ON DELETE CASCADE
);
CREATE INDEX ix_entitlement_plan_quotas_plan_id ON entitlement_plan_quotas (plan_id);
ALTER TABLE gateway_request_logs ADD COLUMN entitlement_plan_id UUID;
ALTER TABLE gateway_request_logs ADD COLUMN provider_plan_id UUID;
CREATE INDEX ix_gateway_request_logs_entitlement_time ON gateway_request_logs (entitlement_plan_id, created_at);
CREATE INDEX ix_gateway_request_logs_provider_plan_time ON gateway_request_logs (provider_plan_id, created_at);
ALTER TABLE gateway_metrics_hourly ADD COLUMN entitlement_plan_id UUID;
ALTER TABLE gateway_metrics_hourly ADD COLUMN provider_plan_id UUID;
ALTER TABLE gateway_metrics_hourly DROP CONSTRAINT uq_gateway_metrics_hourly_dim;
ALTER TABLE gateway_metrics_hourly ADD CONSTRAINT uq_gateway_metrics_hourly_dim UNIQUE (bucket_at, team_id, user_id, vkey_id, credential_id, entitlement_plan_id, provider_plan_id, provider, real_model, capability);
