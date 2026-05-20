-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260522_tenant_phase3.py
-- revision: 20260522_p3
-- down_revision: 20260521_tds
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

ALTER TABLE gateway_models DROP CONSTRAINT uq_gateway_models_team_name;
DROP INDEX ix_gateway_models_lookup;
DROP INDEX ix_gateway_models_team;
ALTER TABLE gateway_models RENAME COLUMN team_id TO tenant_id;
ALTER TABLE gateway_models ALTER COLUMN tenant_id SET NOT NULL;
CREATE INDEX ix_gateway_models_tenant ON gateway_models (tenant_id);
ALTER TABLE gateway_models ADD CONSTRAINT uq_gateway_models_tenant_name UNIQUE (tenant_id, name);
CREATE INDEX ix_gateway_models_lookup ON gateway_models (tenant_id, capability, enabled);
ALTER TABLE gateway_routes DROP CONSTRAINT uq_gateway_routes_team_virtual_model;
DROP INDEX ix_gateway_routes_team;
ALTER TABLE gateway_routes RENAME COLUMN team_id TO tenant_id;
ALTER TABLE gateway_routes ALTER COLUMN tenant_id SET NOT NULL;
CREATE INDEX ix_gateway_routes_tenant ON gateway_routes (tenant_id);
ALTER TABLE gateway_routes ADD CONSTRAINT uq_gateway_routes_tenant_virtual_model UNIQUE (tenant_id, virtual_model);
DROP INDEX ix_gateway_alert_rules_lookup;
DROP INDEX ix_gateway_alert_rules_team;
ALTER TABLE gateway_alert_rules RENAME COLUMN team_id TO tenant_id;
ALTER TABLE gateway_alert_rules ALTER COLUMN tenant_id SET NOT NULL;
CREATE INDEX ix_gateway_alert_rules_tenant ON gateway_alert_rules (tenant_id);
CREATE INDEX ix_gateway_alert_rules_lookup ON gateway_alert_rules (tenant_id, enabled);
DROP INDEX ix_gateway_alert_events_team;
ALTER TABLE gateway_alert_events RENAME COLUMN team_id TO tenant_id;
CREATE INDEX ix_gateway_alert_events_tenant ON gateway_alert_events (tenant_id);
DROP INDEX ix_gateway_request_logs_team_time;
ALTER TABLE gateway_request_logs RENAME COLUMN team_id TO tenant_id;
CREATE INDEX ix_gateway_request_logs_tenant_time ON gateway_request_logs (tenant_id, created_at);
DROP INDEX ix_gateway_metrics_hourly_team_bucket;
ALTER TABLE gateway_metrics_hourly RENAME COLUMN team_id TO tenant_id;
CREATE INDEX ix_gateway_metrics_hourly_tenant_bucket ON gateway_metrics_hourly (tenant_id, bucket_at);
DROP INDEX ix_api_key_gateway_grants_user_team;
DROP INDEX ix_api_key_gateway_grants_team_id;
ALTER TABLE api_key_gateway_grants RENAME COLUMN team_id TO tenant_id;
CREATE INDEX ix_api_key_gateway_grants_tenant_id ON api_key_gateway_grants (tenant_id);
CREATE INDEX ix_api_key_gateway_grants_user_tenant ON api_key_gateway_grants (user_id, tenant_id);
ALTER TABLE api_key_gateway_grants DROP CONSTRAINT uq_api_key_gateway_grants_key_team;
ALTER TABLE api_key_gateway_grants ADD CONSTRAINT uq_api_key_gateway_grants_key_tenant UNIQUE (api_key_id, tenant_id);
DROP INDEX ix_gateway_virtual_keys_team;
ALTER TABLE gateway_virtual_keys RENAME COLUMN team_id TO tenant_id;
ALTER TABLE gateway_virtual_keys ALTER COLUMN tenant_id SET NOT NULL;
CREATE INDEX ix_gateway_virtual_keys_tenant ON gateway_virtual_keys (tenant_id);
DROP INDEX ix_entitlement_plans_active;
ALTER TABLE entitlement_plans RENAME COLUMN scope TO target_kind;
ALTER TABLE entitlement_plans RENAME COLUMN scope_id TO target_id;
CREATE INDEX ix_entitlement_plans_active ON entitlement_plans (target_kind, target_id, is_active, valid_from, valid_until);
