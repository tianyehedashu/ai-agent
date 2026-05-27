-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260527_slow_sql_hotpath_indexes.py
-- revision: 20260527_slow_sql
-- down_revision: f31bf0379153
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

CREATE INDEX IF NOT EXISTS ix_gateway_alert_rules_enabled ON gateway_alert_rules (tenant_id) WHERE enabled IS TRUE;
DROP INDEX IF EXISTS ix_system_gateway_alert_rules_enabled;
CREATE INDEX IF NOT EXISTS ix_system_gateway_alert_rules_enabled ON system_gateway_alert_rules (name) WHERE enabled IS TRUE;
CREATE INDEX IF NOT EXISTS ix_entitlement_plans_lifecycle ON entitlement_plans (valid_until) WHERE is_active IS TRUE;
CREATE INDEX IF NOT EXISTS ix_provider_plans_lifecycle ON provider_plans (valid_until) WHERE is_active IS TRUE;
CREATE INDEX IF NOT EXISTS ix_gateway_request_logs_created_at_brin ON gateway_request_logs USING brin (created_at);
CREATE INDEX IF NOT EXISTS ix_gateway_teams_active_kind_created ON gateway_teams (kind, created_at) WHERE is_active IS TRUE;
