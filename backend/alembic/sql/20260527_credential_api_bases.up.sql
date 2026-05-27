-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260527_credential_api_bases.py
-- revision: 20260527_api_bases
-- down_revision: 20260526_prof
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

ALTER TABLE provider_credentials ADD COLUMN api_bases JSONB;
COMMENT ON COLUMN provider_credentials.api_bases IS '��Э�� endpoint ���ǣ�openai_compat / anthropic_native';
ALTER TABLE system_provider_credentials ADD COLUMN api_bases JSONB;
COMMENT ON COLUMN system_provider_credentials.api_bases IS '��Э�� endpoint ���ǣ�openai_compat / anthropic_native';
UPDATE provider_credentials
        SET api_bases = jsonb_build_object('openai_compat', api_base)
        WHERE api_base IS NOT NULL AND trim(api_base) <> '';
UPDATE system_provider_credentials
        SET api_bases = jsonb_build_object('openai_compat', api_base)
        WHERE api_base IS NOT NULL AND trim(api_base) <> '';
