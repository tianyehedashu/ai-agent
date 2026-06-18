-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260617_vkey_team_grants.py
-- revision: 20260617_vktg
-- down_revision: 20260616_dppi
-- 方向: DOWNGRADE (down.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

DROP INDEX IF EXISTS ix_vkey_team_grants_user_tenant_active;
DROP INDEX IF EXISTS ix_vkey_team_grants_vkey_active;
DROP INDEX IF EXISTS uq_vkey_team_grants_active;
DROP TABLE gateway_virtual_key_team_grants;
