-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260601_drop_legacy_tenant_id_fks.py
-- revision: 20260601_dltif
-- down_revision: 20260531_ort
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

ALTER TABLE gateway_models DROP CONSTRAINT IF EXISTS gateway_models_team_id_fkey;
ALTER TABLE gateway_models DROP CONSTRAINT IF EXISTS gateway_models_tenant_id_fkey;
ALTER TABLE gateway_routes DROP CONSTRAINT IF EXISTS gateway_routes_team_id_fkey;
ALTER TABLE gateway_routes DROP CONSTRAINT IF EXISTS gateway_routes_tenant_id_fkey;
ALTER TABLE gateway_alert_rules DROP CONSTRAINT IF EXISTS gateway_alert_rules_team_id_fkey;
ALTER TABLE gateway_alert_rules DROP CONSTRAINT IF EXISTS gateway_alert_rules_tenant_id_fkey;
ALTER TABLE gateway_virtual_keys DROP CONSTRAINT IF EXISTS gateway_virtual_keys_team_id_fkey;
ALTER TABLE gateway_virtual_keys DROP CONSTRAINT IF EXISTS gateway_virtual_keys_tenant_id_fkey;
