-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic downgrade -1
-- versions/20260703_metrics_hourly_resource_owner_dim.py
-- revision: 20260703_mhro
-- down_revision: 20260702_rtg
-- 方向: DOWNGRADE (down.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

ALTER TABLE gateway_metrics_hourly DROP CONSTRAINT uq_gateway_metrics_hourly_dim;
ALTER TABLE gateway_metrics_hourly ADD CONSTRAINT uq_gateway_metrics_hourly_dim UNIQUE (bucket_at, tenant_id, user_id, vkey_id, credential_id, entitlement_plan_id, provider_plan_id, provider, model_key, capability);
