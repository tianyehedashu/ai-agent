-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic downgrade -1  （走 alembic/versions/*.py）
-- versions/20260704_add_limit_images.py
-- revision: 20260704_lim
-- down_revision: 20260703_mhro
-- 方向: DOWNGRADE (down.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

ALTER TABLE gateway_request_logs DROP COLUMN image_count;
ALTER TABLE provider_quotas DROP COLUMN limit_images;
ALTER TABLE entitlement_plan_quotas DROP COLUMN limit_images;
ALTER TABLE gateway_budgets DROP COLUMN current_images;
ALTER TABLE gateway_budgets DROP COLUMN limit_images;
