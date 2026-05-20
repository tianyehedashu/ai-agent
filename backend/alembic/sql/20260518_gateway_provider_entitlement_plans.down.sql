-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260518_gateway_provider_entitlement_plans.py
-- revision: 20260518_gpep
-- down_revision: 20260515_drop_pc_lum
-- 方向: DOWNGRADE (down.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

ALTER TABLE gateway_metrics_hourly DROP CONSTRAINT uq_gateway_metrics_hourly_dim;
ALTER TABLE gateway_metrics_hourly ADD CONSTRAINT uq_gateway_metrics_hourly_dim UNIQUE (bucket_at, team_id, user_id, vkey_id, credential_id, provider, real_model, capability);
ALTER TABLE gateway_metrics_hourly DROP COLUMN provider_plan_id;
ALTER TABLE gateway_metrics_hourly DROP COLUMN entitlement_plan_id;
DROP INDEX ix_gateway_request_logs_provider_plan_time;
DROP INDEX ix_gateway_request_logs_entitlement_time;
ALTER TABLE gateway_request_logs DROP COLUMN provider_plan_id;
ALTER TABLE gateway_request_logs DROP COLUMN entitlement_plan_id;
DROP INDEX ix_entitlement_plan_quotas_plan_id;
DROP TABLE entitlement_plan_quotas;
DROP INDEX ix_entitlement_plans_active;
DROP INDEX ix_entitlement_plans_scope_id;
DROP TABLE entitlement_plans;
DROP INDEX ix_provider_plan_quotas_plan_id;
DROP TABLE provider_plan_quotas;
DROP INDEX ix_provider_plans_active;
DROP INDEX ix_provider_plans_credential_id;
DROP TABLE provider_plans;
