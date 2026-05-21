-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260526_provider_credentials_tenant_id.py
-- revision: 20260526_pct
-- down_revision: 20260525_dso
-- 方向: DOWNGRADE (down.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

DROP INDEX uq_provider_credentials_user_scope_name;
DROP INDEX uq_provider_credentials_tenant_provider_name;
UPDATE provider_credentials
        SET scope = 'team', scope_id = tenant_id
        WHERE tenant_id IS NOT NULL AND scope IS NULL;
DROP INDEX ix_provider_credentials_tenant_id;
ALTER TABLE provider_credentials DROP COLUMN tenant_id;
ALTER TABLE provider_credentials ADD CONSTRAINT uq_provider_credentials_scope_name UNIQUE (scope, scope_id, provider, name);
