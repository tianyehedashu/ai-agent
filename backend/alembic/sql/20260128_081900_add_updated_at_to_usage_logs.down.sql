-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260128_081900_add_updated_at_to_usage_logs.py
-- revision: e3f4g5h6i7j8
-- down_revision: d2e3f4g5h6i7
-- 方向: DOWNGRADE (down.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

ALTER TABLE api_key_usage_logs DROP COLUMN updated_at;
