-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260704_add_limit_images.py
-- revision: 20260704_lim
-- down_revision: 20260703_mhro
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

-- gateway_budgets：图片生成张数限额 + 当前用量
ALTER TABLE gateway_budgets ADD COLUMN limit_images INTEGER;
ALTER TABLE gateway_budgets ADD COLUMN current_images INTEGER NOT NULL DEFAULT 0;

-- entitlement_plan_quotas：图片生成张数限额
ALTER TABLE entitlement_plan_quotas ADD COLUMN limit_images INTEGER;

-- provider_quotas：图片生成张数限额
ALTER TABLE provider_quotas ADD COLUMN limit_images INTEGER;

-- gateway_request_logs：单次调用生成图片张数（分区主表加列，PG 15+ 自动级联子分区）
ALTER TABLE gateway_request_logs ADD COLUMN image_count INTEGER NOT NULL DEFAULT 0;
