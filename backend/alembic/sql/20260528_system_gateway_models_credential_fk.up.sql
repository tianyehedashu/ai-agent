-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260528_system_gateway_models_credential_fk.py
-- revision: 20260528_sgmcf
-- down_revision: 20260527_pcn
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

INSERT INTO system_provider_credentials (
            id, provider, name, api_key_encrypted, api_base, extra,
            is_active, created_at, updated_at
        )
        SELECT
            pc.id, pc.provider, pc.name, pc.api_key_encrypted, pc.api_base, pc.extra,
            pc.is_active, pc.created_at, pc.updated_at
        FROM provider_credentials pc
        WHERE pc.scope = 'system'
          AND NOT EXISTS (
            SELECT 1 FROM system_provider_credentials spc WHERE spc.id = pc.id
          )
        ON CONFLICT (id) DO NOTHING;
UPDATE system_gateway_models sgm
        SET credential_id = spc.id
        FROM provider_credentials pc
        JOIN system_provider_credentials spc
          ON spc.provider = pc.provider AND spc.name = pc.name
        WHERE sgm.credential_id = pc.id
          AND NOT EXISTS (
            SELECT 1 FROM system_provider_credentials x WHERE x.id = sgm.credential_id
          );
UPDATE gateway_models gm
        SET credential_id = spc.id
        FROM provider_credentials pc
        JOIN system_provider_credentials spc ON spc.id = pc.id
        WHERE gm.credential_id = pc.id
          AND pc.scope = 'system';
DELETE FROM provider_credentials pc
        WHERE pc.scope = 'system'
          AND EXISTS (
            SELECT 1 FROM system_provider_credentials spc WHERE spc.id = pc.id
          )
          AND NOT EXISTS (
            SELECT 1 FROM gateway_models gm WHERE gm.credential_id = pc.id
          );
DO $$
        DECLARE
            fk_name text;
        BEGIN
            SELECT c.conname INTO fk_name
            FROM pg_constraint c
            JOIN pg_class t ON c.conrelid = t.oid
            WHERE t.relname = 'system_gateway_models'
              AND c.contype = 'f'
              AND pg_get_constraintdef(c.oid) LIKE '%provider_credentials%';
            IF fk_name IS NOT NULL THEN
                EXECUTE format(
                    'ALTER TABLE system_gateway_models DROP CONSTRAINT %I', fk_name
                );
            END IF;
        END $$;;
ALTER TABLE system_gateway_models ADD CONSTRAINT fk_system_gateway_models_credential_id FOREIGN KEY(credential_id) REFERENCES system_provider_credentials (id) ON DELETE RESTRICT;
