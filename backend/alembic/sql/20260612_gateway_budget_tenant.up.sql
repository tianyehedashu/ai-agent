-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260612_gateway_budget_tenant.py
-- revision: 20260612_gbt
-- down_revision: 20260611_gbc
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

ALTER TABLE gateway_budgets ADD COLUMN tenant_id UUID;
CREATE INDEX ix_gateway_budgets_tenant_id ON gateway_budgets (tenant_id);
DROP INDEX uq_gateway_budgets_target_period_agg;
DROP INDEX uq_gateway_budgets_target_period_model;
CREATE UNIQUE INDEX uq_gateway_budgets_target_period_agg ON gateway_budgets (target_kind, target_id, coalesce(tenant_id, '00000000-0000-0000-0000-000000000000'::uuid), period) WHERE model_name IS NULL AND credential_id IS NULL;
CREATE UNIQUE INDEX uq_gateway_budgets_target_period_model ON gateway_budgets (target_kind, target_id, coalesce(tenant_id, '00000000-0000-0000-0000-000000000000'::uuid), period, model_name) WHERE model_name IS NOT NULL AND credential_id IS NULL;
