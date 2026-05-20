-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260514_gateway_budget_model_name.py
-- revision: 20260514_gbm
-- down_revision: 20260514_dsw
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

ALTER TABLE gateway_budgets ADD COLUMN model_name VARCHAR(200);
ALTER TABLE gateway_budgets DROP CONSTRAINT uq_gateway_budgets_scope_period;
CREATE UNIQUE INDEX uq_gateway_budgets_scope_period_agg ON gateway_budgets (scope, scope_id, period) WHERE model_name IS NULL;
CREATE UNIQUE INDEX uq_gateway_budgets_scope_period_model ON gateway_budgets (scope, scope_id, period, model_name) WHERE model_name IS NOT NULL;
