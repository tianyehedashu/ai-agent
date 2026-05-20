-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260514_gateway_budget_model_name.py
-- revision: 20260514_gbm
-- down_revision: 20260514_dsw
-- 方向: DOWNGRADE (down.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

DROP INDEX uq_gateway_budgets_scope_period_model;
DROP INDEX uq_gateway_budgets_scope_period_agg;
ALTER TABLE gateway_budgets ADD CONSTRAINT uq_gateway_budgets_scope_period UNIQUE (scope, scope_id, period);
ALTER TABLE gateway_budgets DROP COLUMN model_name;
