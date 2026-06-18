-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260627_quota_row_enable_window.py
-- revision: 20260627_qrew
-- down_revision: 20260626_r2c
-- 方向: DOWNGRADE (down.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

ALTER TABLE gateway_budgets DROP COLUMN valid_until;
ALTER TABLE gateway_budgets DROP COLUMN valid_from;
ALTER TABLE gateway_budgets DROP COLUMN enabled;
ALTER TABLE provider_plan_quotas DROP COLUMN valid_until;
ALTER TABLE provider_plan_quotas DROP COLUMN valid_from;
ALTER TABLE provider_plan_quotas DROP COLUMN enabled;
ALTER TABLE entitlement_plan_quotas DROP COLUMN valid_until;
ALTER TABLE entitlement_plan_quotas DROP COLUMN valid_from;
ALTER TABLE entitlement_plan_quotas DROP COLUMN enabled;
