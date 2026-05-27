-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260526_credential_profile_call_shape.py
-- revision: 20260526_prof
-- down_revision: 20260605_sys_cred_models
-- 方向: DOWNGRADE (down.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

ALTER TABLE system_gateway_models DROP COLUMN upstream_call_shape;
ALTER TABLE gateway_models DROP COLUMN upstream_call_shape;
ALTER TABLE system_provider_credentials DROP COLUMN profile_id;
ALTER TABLE provider_credentials DROP COLUMN profile_id;
