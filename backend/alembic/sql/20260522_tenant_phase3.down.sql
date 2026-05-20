-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260522_tenant_phase3.py
-- revision: 20260522_p3
-- down_revision: 20260521_tds
-- 方向: DOWNGRADE (down.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

DROP INDEX ix_entitlement_plans_active;
ALTER TABLE entitlement_plans RENAME COLUMN target_id TO scope_id;
ALTER TABLE entitlement_plans RENAME COLUMN target_kind TO scope;
CREATE INDEX ix_entitlement_plans_active ON entitlement_plans (scope, scope_id, is_active, valid_from, valid_until);
DROP INDEX ix_gateway_virtual_keys_tenant;
ALTER TABLE gateway_virtual_keys RENAME COLUMN tenant_id TO team_id;
ALTER TABLE gateway_virtual_keys ALTER COLUMN team_id DROP NOT NULL;
CREATE INDEX ix_gateway_virtual_keys_team ON gateway_virtual_keys (team_id);
DROP INDEX ix_api_key_gateway_grants_tenant;
ALTER TABLE api_key_gateway_grants RENAME COLUMN tenant_id TO team_id;
CREATE INDEX ix_api_key_gateway_grants_team ON api_key_gateway_grants (team_id);
DROP INDEX ix_gateway_metrics_hourly_tenant;
ALTER TABLE gateway_metrics_hourly RENAME COLUMN tenant_id TO team_id;
CREATE INDEX ix_gateway_metrics_hourly_team ON gateway_metrics_hourly (team_id);
DROP INDEX ix_gateway_request_logs_tenant;
ALTER TABLE gateway_request_logs RENAME COLUMN tenant_id TO team_id;
CREATE INDEX ix_gateway_request_logs_team ON gateway_request_logs (team_id);
DROP INDEX ix_gateway_alert_events_tenant;
ALTER TABLE gateway_alert_events RENAME COLUMN tenant_id TO team_id;
CREATE INDEX ix_gateway_alert_events_team ON gateway_alert_events (team_id);
DROP INDEX ix_gateway_alert_rules_lookup;
DROP INDEX ix_gateway_alert_rules_tenant;
ALTER TABLE gateway_alert_rules RENAME COLUMN tenant_id TO team_id;
ALTER TABLE gateway_alert_rules ALTER COLUMN team_id DROP NOT NULL;
CREATE INDEX ix_gateway_alert_rules_team ON gateway_alert_rules (team_id);
CREATE INDEX ix_gateway_alert_rules_lookup ON gateway_alert_rules (team_id, enabled);
ALTER TABLE gateway_routes DROP CONSTRAINT uq_gateway_routes_tenant_virtual_model;
DROP INDEX ix_gateway_routes_tenant;
ALTER TABLE gateway_routes RENAME COLUMN tenant_id TO team_id;
ALTER TABLE gateway_routes ALTER COLUMN team_id DROP NOT NULL;
CREATE INDEX ix_gateway_routes_team ON gateway_routes (team_id);
ALTER TABLE gateway_routes ADD CONSTRAINT uq_gateway_routes_team_virtual_model UNIQUE (team_id, virtual_model);
DROP INDEX ix_gateway_models_lookup;
ALTER TABLE gateway_models DROP CONSTRAINT uq_gateway_models_tenant_name;
DROP INDEX ix_gateway_models_tenant;
ALTER TABLE gateway_models RENAME COLUMN tenant_id TO team_id;
ALTER TABLE gateway_models ALTER COLUMN team_id DROP NOT NULL;
CREATE INDEX ix_gateway_models_team ON gateway_models (team_id);
ALTER TABLE gateway_models ADD CONSTRAINT uq_gateway_models_team_name UNIQUE (team_id, name);
CREATE INDEX ix_gateway_models_lookup ON gateway_models (team_id, capability, enabled);
