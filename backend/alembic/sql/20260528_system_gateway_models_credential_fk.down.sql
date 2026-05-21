-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260528_system_gateway_models_credential_fk.py
-- revision: 20260528_sgmcf
-- down_revision: 20260527_pcn
-- 方向: DOWNGRADE (down.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

ALTER TABLE system_gateway_models DROP CONSTRAINT fk_system_gateway_models_credential_id;
INSERT INTO provider_credentials (
            id, tenant_id, scope, scope_id, provider, name, api_key_encrypted,
            api_base, extra, is_active, created_at, updated_at
        )
        SELECT
            spc.id, NULL, 'system', NULL, spc.provider, spc.name, spc.api_key_encrypted,
            spc.api_base, spc.extra, spc.is_active, spc.created_at, spc.updated_at
        FROM system_provider_credentials spc
        WHERE NOT EXISTS (
            SELECT 1 FROM provider_credentials pc WHERE pc.id = spc.id
        );
ALTER TABLE system_gateway_models ADD CONSTRAINT fk_system_gateway_models_credential_id_pc FOREIGN KEY(credential_id) REFERENCES provider_credentials (id) ON DELETE RESTRICT;
