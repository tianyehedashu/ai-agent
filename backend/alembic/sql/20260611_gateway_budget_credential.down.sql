-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260611_gateway_budget_credential.py
-- revision: 20260611_gbc
-- down_revision: 20260610_del_probe_logs
-- 方向: DOWNGRADE (down.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

DROP INDEX uq_gateway_budgets_target_period_cred_model;
DROP INDEX uq_gateway_budgets_target_period_cred_agg;
DROP INDEX uq_gateway_budgets_target_period_model;
DROP INDEX uq_gateway_budgets_target_period_agg;
CREATE UNIQUE INDEX uq_gateway_budgets_target_period_agg ON gateway_budgets (target_kind, target_id, period) WHERE model_name IS NULL;
CREATE UNIQUE INDEX uq_gateway_budgets_target_period_model ON gateway_budgets (target_kind, target_id, period, model_name) WHERE model_name IS NOT NULL;
DROP INDEX ix_gateway_budgets_credential_id;
ALTER TABLE gateway_budgets DROP COLUMN credential_id;
