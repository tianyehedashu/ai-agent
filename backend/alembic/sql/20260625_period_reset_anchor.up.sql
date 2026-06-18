-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260625_period_reset_anchor.py
-- revision: 20260625_pra
-- down_revision: 20260624_gmhrp
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

ALTER TABLE gateway_budgets ADD COLUMN period_timezone VARCHAR(64) DEFAULT 'UTC' NOT NULL;
ALTER TABLE gateway_budgets ADD COLUMN period_reset_minutes SMALLINT DEFAULT '0' NOT NULL;
ALTER TABLE gateway_budgets ADD COLUMN period_reset_day SMALLINT DEFAULT '1' NOT NULL;
ALTER TABLE provider_plan_quotas ADD COLUMN reset_timezone VARCHAR(64) DEFAULT 'UTC' NOT NULL;
ALTER TABLE provider_plan_quotas ADD COLUMN reset_time_minutes SMALLINT DEFAULT '0' NOT NULL;
ALTER TABLE provider_plan_quotas ADD COLUMN reset_day_of_month SMALLINT DEFAULT '1' NOT NULL;
ALTER TABLE entitlement_plan_quotas ADD COLUMN reset_timezone VARCHAR(64) DEFAULT 'UTC' NOT NULL;
ALTER TABLE entitlement_plan_quotas ADD COLUMN reset_time_minutes SMALLINT DEFAULT '0' NOT NULL;
ALTER TABLE entitlement_plan_quotas ADD COLUMN reset_day_of_month SMALLINT DEFAULT '1' NOT NULL;
