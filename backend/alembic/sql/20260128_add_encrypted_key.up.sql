-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260128_add_encrypted_key.py
-- revision: d2e3f4g5h6i7
-- down_revision: c1d2e3f4g5h6
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

ALTER TABLE api_keys ADD COLUMN encrypted_key VARCHAR(512);
UPDATE api_keys SET encrypted_key = 'legacy_key' WHERE encrypted_key IS NULL;
ALTER TABLE api_keys ALTER COLUMN encrypted_key SET NOT NULL;
