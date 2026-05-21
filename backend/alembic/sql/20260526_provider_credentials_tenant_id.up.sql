-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260526_provider_credentials_tenant_id.py
-- revision: 20260526_pct
-- down_revision: 20260525_dso
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

ALTER TABLE provider_credentials ADD COLUMN tenant_id UUID;
CREATE INDEX ix_provider_credentials_tenant_id ON provider_credentials (tenant_id);
UPDATE provider_credentials
        SET tenant_id = scope_id
        WHERE scope = 'team' AND scope_id IS NOT NULL;
DELETE FROM provider_credentials pc
        WHERE pc.scope = 'system'
          AND NOT EXISTS (SELECT 1 FROM gateway_models gm WHERE gm.credential_id = pc.id)
          AND NOT EXISTS (
              SELECT 1 FROM system_gateway_models sgm WHERE sgm.credential_id = pc.id
          );
UPDATE provider_credentials
        SET scope = NULL, scope_id = NULL
        WHERE scope = 'team';
ALTER TABLE provider_credentials DROP CONSTRAINT uq_provider_credentials_scope_name;
CREATE UNIQUE INDEX uq_provider_credentials_tenant_provider_name ON provider_credentials (tenant_id, provider, name) WHERE tenant_id IS NOT NULL;
CREATE UNIQUE INDEX uq_provider_credentials_user_scope_name ON provider_credentials (scope, scope_id, provider, name) WHERE scope = 'user';
