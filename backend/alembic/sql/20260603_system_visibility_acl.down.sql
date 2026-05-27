-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260603_system_visibility_acl.py
-- revision: 20260603_svac
-- down_revision: 20260602_dafk
-- 方向: DOWNGRADE (down.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

DROP INDEX ix_system_gateway_grants_target;
DROP INDEX ix_system_gateway_grants_subject;
DROP TABLE system_gateway_grants;
ALTER TABLE system_gateway_models DROP COLUMN visibility;
ALTER TABLE system_provider_credentials DROP COLUMN visibility;
