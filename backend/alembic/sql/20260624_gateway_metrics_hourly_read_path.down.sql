-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260624_gateway_metrics_hourly_read_path.py
-- revision: 20260624_gmhrp
-- down_revision: 20260623_apprm
-- 方向: DOWNGRADE (down.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

DROP TABLE gateway_rollup_state;
ALTER TABLE gateway_metrics_hourly DROP CONSTRAINT uq_gateway_metrics_hourly_dim;
ALTER TABLE gateway_metrics_hourly ADD CONSTRAINT uq_gateway_metrics_hourly_dim UNIQUE (bucket_at, tenant_id, user_id, vkey_id, credential_id, entitlement_plan_id, provider_plan_id, provider, real_model, capability);
ALTER TABLE gateway_metrics_hourly DROP COLUMN model_key;
ALTER TABLE gateway_metrics_hourly DROP COLUMN ttfb_total_ms;
ALTER TABLE gateway_metrics_hourly DROP COLUMN revenue_usd;
