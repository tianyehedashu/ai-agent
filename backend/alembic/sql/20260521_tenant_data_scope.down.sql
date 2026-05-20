-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260521_tenant_data_scope.py
-- revision: 20260521_tds
-- down_revision: 20260520_ssc_uq
-- 方向: DOWNGRADE (down.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

INSERT INTO gateway_models (
            id, team_id, name, capability, real_model, credential_id, provider,
            weight, rpm_limit, tpm_limit, enabled, tags,
            last_test_status, last_tested_at, last_test_reason,
            created_at, updated_at
        )
        SELECT
            id, NULL, name, capability, real_model, credential_id, provider,
            weight, rpm_limit, tpm_limit, enabled, tags,
            last_test_status, last_tested_at, last_test_reason,
            created_at, updated_at
        FROM system_gateway_models;
DROP TABLE system_gateway_models;
INSERT INTO gateway_routes (
            id, team_id, virtual_model, primary_models, fallbacks_general,
            fallbacks_content_policy, fallbacks_context_window,
            strategy, retry_policy, enabled, created_at, updated_at
        )
        SELECT
            id, NULL, virtual_model, primary_models, fallbacks_general,
            fallbacks_content_policy, fallbacks_context_window,
            strategy, retry_policy, enabled, created_at, updated_at
        FROM system_gateway_routes;
DROP TABLE system_gateway_routes;
INSERT INTO gateway_alert_rules (
            id, team_id, name, description, metric, threshold, window_minutes,
            channels, enabled, last_triggered_at, created_at, updated_at
        )
        SELECT
            id, NULL, name, description, metric, threshold, window_minutes,
            channels, enabled, last_triggered_at, created_at, updated_at
        FROM system_gateway_alert_rules;
DROP TABLE system_gateway_alert_rules;
INSERT INTO provider_credentials (
            id, scope, scope_id, provider, name, api_key_encrypted,
            api_base, extra, is_active, created_at, updated_at
        )
        SELECT
            id, 'system', NULL, provider, name, api_key_encrypted,
            api_base, extra, is_active, created_at, updated_at
        FROM system_provider_credentials;
DROP TABLE system_provider_credentials;
