-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260529_gateway_budgets_rename_to_target.py
-- revision: 20260529_gbrt
-- down_revision: 20260528_sgmcf
-- 方向: DOWNGRADE (down.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

ALTER INDEX ix_gateway_budgets_target_lookup RENAME TO ix_gateway_budgets_lookup;
ALTER INDEX uq_gateway_budgets_target_period_model RENAME TO uq_gateway_budgets_scope_period_model;
ALTER INDEX uq_gateway_budgets_target_period_agg RENAME TO uq_gateway_budgets_scope_period_agg;
UPDATE gateway_budgets SET target_kind = 'team' WHERE target_kind = 'tenant';
ALTER TABLE gateway_budgets RENAME target_id TO scope_id;
ALTER TABLE gateway_budgets RENAME target_kind TO scope;
