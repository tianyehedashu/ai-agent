-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260527_provider_credentials_scope_nullable.py
-- revision: 20260527_pcn
-- down_revision: 20260526_pct
-- 方向: DOWNGRADE (down.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

UPDATE provider_credentials
        SET scope = 'team'
        WHERE tenant_id IS NOT NULL AND scope IS NULL;
ALTER TABLE provider_credentials ALTER COLUMN scope SET NOT NULL;
