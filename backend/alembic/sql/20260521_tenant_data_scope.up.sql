-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260521_tenant_data_scope.py
-- revision: 20260521_tds
-- down_revision: 20260520_ssc_uq
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

CREATE TABLE system_gateway_models (
    id UUID NOT NULL, 
    name VARCHAR(200) NOT NULL, 
    capability VARCHAR(40) NOT NULL, 
    real_model VARCHAR(200) NOT NULL, 
    credential_id UUID NOT NULL, 
    provider VARCHAR(50) NOT NULL, 
    weight INTEGER DEFAULT '1' NOT NULL, 
    rpm_limit INTEGER, 
    tpm_limit INTEGER, 
    enabled BOOLEAN DEFAULT 'true' NOT NULL, 
    tags JSONB, 
    last_test_status VARCHAR(20), 
    last_tested_at TIMESTAMP WITH TIME ZONE, 
    last_test_reason TEXT, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_system_gateway_models_name UNIQUE (name)
);
CREATE INDEX ix_system_gateway_models_lookup ON system_gateway_models (capability, enabled);
INSERT INTO system_gateway_models (
            id, name, capability, real_model, credential_id, provider,
            weight, rpm_limit, tpm_limit, enabled, tags,
            last_test_status, last_tested_at, last_test_reason,
            created_at, updated_at
        )
        SELECT
            id, name, capability, real_model, credential_id, provider,
            weight, rpm_limit, tpm_limit, enabled, tags,
            last_test_status, last_tested_at, last_test_reason,
            created_at, updated_at
        FROM gateway_models
        WHERE team_id IS NULL;
DELETE FROM gateway_models WHERE team_id IS NULL;
CREATE TABLE system_gateway_routes (
    id UUID NOT NULL, 
    virtual_model VARCHAR(200) NOT NULL, 
    primary_models VARCHAR(200)[] NOT NULL, 
    fallbacks_general VARCHAR(200)[] NOT NULL, 
    fallbacks_content_policy VARCHAR(200)[] NOT NULL, 
    fallbacks_context_window VARCHAR(200)[] NOT NULL, 
    strategy VARCHAR(40) DEFAULT 'simple-shuffle' NOT NULL, 
    retry_policy JSONB, 
    enabled BOOLEAN DEFAULT 'true' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_system_gateway_routes_virtual_model UNIQUE (virtual_model)
);
INSERT INTO system_gateway_routes (
            id, virtual_model, primary_models, fallbacks_general,
            fallbacks_content_policy, fallbacks_context_window,
            strategy, retry_policy, enabled, created_at, updated_at
        )
        SELECT
            id, virtual_model, primary_models, fallbacks_general,
            fallbacks_content_policy, fallbacks_context_window,
            strategy, retry_policy, enabled, created_at, updated_at
        FROM gateway_routes
        WHERE team_id IS NULL;
DELETE FROM gateway_routes WHERE team_id IS NULL;
CREATE TABLE system_gateway_alert_rules (
    id UUID NOT NULL, 
    name VARCHAR(100) NOT NULL, 
    description TEXT, 
    metric VARCHAR(40) NOT NULL, 
    threshold NUMERIC(12, 4) NOT NULL, 
    window_minutes INTEGER DEFAULT '5' NOT NULL, 
    channels JSONB NOT NULL, 
    enabled BOOLEAN DEFAULT 'true' NOT NULL, 
    last_triggered_at TIMESTAMP WITH TIME ZONE, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id)
);
INSERT INTO system_gateway_alert_rules (
            id, name, description, metric, threshold, window_minutes,
            channels, enabled, last_triggered_at, created_at, updated_at
        )
        SELECT
            id, name, description, metric, threshold, window_minutes,
            channels, enabled, last_triggered_at, created_at, updated_at
        FROM gateway_alert_rules
        WHERE team_id IS NULL;
DELETE FROM gateway_alert_rules WHERE team_id IS NULL;
CREATE TABLE system_provider_credentials (
    id UUID NOT NULL, 
    provider VARCHAR(50) NOT NULL, 
    name VARCHAR(100) NOT NULL, 
    api_key_encrypted TEXT NOT NULL, 
    api_base VARCHAR(500), 
    extra JSONB, 
    is_active BOOLEAN DEFAULT 'true' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_system_provider_credentials_provider_name UNIQUE (provider, name)
);
INSERT INTO system_provider_credentials (
            id, provider, name, api_key_encrypted, api_base, extra,
            is_active, created_at, updated_at
        )
        SELECT
            id, provider, name, api_key_encrypted, api_base, extra,
            is_active, created_at, updated_at
        FROM provider_credentials
        WHERE scope = 'system';
DELETE FROM provider_credentials pc
        WHERE pc.scope = 'system'
          AND NOT EXISTS (
            SELECT 1 FROM gateway_models gm WHERE gm.credential_id = pc.id
          )
          AND NOT EXISTS (
            SELECT 1 FROM system_gateway_models sgm WHERE sgm.credential_id = pc.id
          );
