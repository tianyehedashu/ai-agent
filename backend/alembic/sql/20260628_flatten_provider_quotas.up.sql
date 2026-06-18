-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260628_flatten_provider_quotas.py
-- revision: 20260628_fpq
-- down_revision: 20260627_qrew
-- 方向: UPGRADE (up.sql)
-- =============================================================================

CREATE TABLE provider_quotas (
    id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
    credential_id UUID NOT NULL,
    real_model VARCHAR(200),
    label VARCHAR(40) NOT NULL,
    window_seconds INTEGER NOT NULL,
    reset_strategy VARCHAR(32) DEFAULT 'rolling' NOT NULL,
    reset_timezone VARCHAR(64) DEFAULT 'UTC' NOT NULL,
    reset_time_minutes INTEGER DEFAULT 0 NOT NULL,
    reset_day_of_month INTEGER DEFAULT 1 NOT NULL,
    limit_usd NUMERIC(12, 4),
    limit_tokens INTEGER,
    limit_requests INTEGER,
    enabled BOOLEAN DEFAULT true NOT NULL,
    valid_from TIMESTAMP WITH TIME ZONE,
    valid_until TIMESTAMP WITH TIME ZONE,
    PRIMARY KEY (id)
);
CREATE UNIQUE INDEX uq_provider_quota_cred_model_label ON provider_quotas (credential_id, COALESCE(real_model, ''), label);
CREATE INDEX ix_provider_quotas_cred_model_enabled ON provider_quotas (credential_id, real_model, enabled);
CREATE INDEX ix_provider_quotas_credential_id ON provider_quotas (credential_id);

DROP TABLE provider_plan_quotas;
DROP TABLE provider_plans;

DROP INDEX IF EXISTS ix_entitlement_plans_lifecycle;
ALTER TABLE entitlement_plans DROP COLUMN IF EXISTS auto_renew;
ALTER TABLE entitlement_plans DROP COLUMN IF EXISTS valid_until;
ALTER TABLE entitlement_plans DROP COLUMN IF EXISTS is_active;
