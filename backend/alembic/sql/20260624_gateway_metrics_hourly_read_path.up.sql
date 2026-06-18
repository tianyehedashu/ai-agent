-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260624_gateway_metrics_hourly_read_path.py
-- revision: 20260624_gmhrp
-- down_revision: 20260623_apprm
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

ALTER TABLE gateway_metrics_hourly ADD COLUMN revenue_usd NUMERIC(14, 6) DEFAULT '0' NOT NULL;
ALTER TABLE gateway_metrics_hourly ADD COLUMN ttfb_total_ms INTEGER DEFAULT '0' NOT NULL;
ALTER TABLE gateway_metrics_hourly ADD COLUMN model_key VARCHAR(200);
UPDATE gateway_metrics_hourly
        SET model_key = COALESCE(NULLIF(TRIM(real_model), ''), 'unknown')
        WHERE model_key IS NULL;
ALTER TABLE gateway_metrics_hourly ALTER COLUMN model_key SET NOT NULL;
ALTER TABLE gateway_metrics_hourly DROP CONSTRAINT uq_gateway_metrics_hourly_dim;
ALTER TABLE gateway_metrics_hourly ADD CONSTRAINT uq_gateway_metrics_hourly_dim UNIQUE (bucket_at, tenant_id, user_id, vkey_id, credential_id, entitlement_plan_id, provider_plan_id, provider, model_key, capability);
CREATE TABLE gateway_rollup_state (
    id SMALLSERIAL NOT NULL, 
    last_rolled_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_gateway_rollup_state_singleton CHECK (id = 1)
);
INSERT INTO gateway_rollup_state (id, last_rolled_at)
        VALUES (1, date_trunc('hour', NOW() AT TIME ZONE 'UTC') - INTERVAL '48 hours');
