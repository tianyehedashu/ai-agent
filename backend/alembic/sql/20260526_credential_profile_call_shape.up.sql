-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260526_credential_profile_call_shape.py
-- revision: 20260526_prof
-- down_revision: 20260605_sys_cred_models
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

ALTER TABLE provider_credentials ADD COLUMN profile_id VARCHAR(64);
COMMENT ON COLUMN provider_credentials.profile_id IS '���η��� ID���� volcengine.coding_plan����NULL ��ʾ provider.default';
ALTER TABLE system_provider_credentials ADD COLUMN profile_id VARCHAR(64);
COMMENT ON COLUMN system_provider_credentials.profile_id IS '���η��� ID��NULL ��ʾ provider.default';
ALTER TABLE gateway_models ADD COLUMN upstream_call_shape VARCHAR(32);
COMMENT ON COLUMN gateway_models.upstream_call_shape IS '��վ LiteLLM �����Σ�openai_compat / anthropic_native';
ALTER TABLE system_gateway_models ADD COLUMN upstream_call_shape VARCHAR(32);
COMMENT ON COLUMN system_gateway_models.upstream_call_shape IS '��վ LiteLLM �����Σ�openai_compat / anthropic_native';
