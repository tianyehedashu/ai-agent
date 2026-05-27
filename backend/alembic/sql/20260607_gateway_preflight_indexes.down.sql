-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260607_gateway_preflight_indexes.py
-- revision: 20260607_gw_pref_idx
-- down_revision: 20260606_anon_tenant
-- 方向: DOWNGRADE (down.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

DROP INDEX IF EXISTS ix_gateway_budgets_plan_lookup;
DROP INDEX IF EXISTS ix_gateway_routes_tenant_virtual_enabled;
DROP INDEX IF EXISTS ix_system_gateway_grants_target_enabled;
