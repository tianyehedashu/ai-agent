-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260128_090000_drop_api_key_foreign_keys.py
-- revision: f4g5h6i7j8k9
-- down_revision: e3f4g5h6i7j8
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

ALTER TABLE api_keys DROP CONSTRAINT api_keys_user_id_fkey;
ALTER TABLE api_key_usage_logs DROP CONSTRAINT api_key_usage_logs_api_key_id_fkey;
