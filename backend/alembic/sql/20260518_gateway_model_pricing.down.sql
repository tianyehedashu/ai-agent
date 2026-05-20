-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260518_gateway_model_pricing.py
-- revision: 20260518_gmp
-- down_revision: 20260518_gpep
-- 方向: DOWNGRADE (down.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

ALTER TABLE gateway_budgets DROP COLUMN budget_reset_at;
ALTER TABLE gateway_budgets DROP COLUMN max_parallel_requests;
ALTER TABLE gateway_budgets DROP COLUMN soft_limit_usd;
ALTER TABLE gateway_request_logs DROP COLUMN pricing_snapshot;
ALTER TABLE gateway_request_logs DROP COLUMN revenue_usd;
DROP TABLE downstream_model_pricing;
DROP TABLE upstream_model_pricing;
