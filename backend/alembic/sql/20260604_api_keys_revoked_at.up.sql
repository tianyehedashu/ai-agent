-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260604_api_keys_revoked_at.py
-- revision: 20260604_revoked
-- down_revision: 20260603_svac
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

ALTER TABLE api_keys ADD COLUMN revoked_at TIMESTAMP WITH TIME ZONE;
COMMENT ON COLUMN api_keys.revoked_at IS '����ʱ�䣻�ǿձ�ʾ���ó�����������������';
CREATE INDEX ix_api_keys_revoked_at ON api_keys (revoked_at);
UPDATE api_keys
            SET revoked_at = updated_at
            WHERE is_active = false;
