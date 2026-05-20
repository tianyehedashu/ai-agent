-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260508_add_provider_credentials.py
-- revision: 20260508_pc
-- down_revision: a3f8c2d1e4b7
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

CREATE TABLE provider_credentials (
    id UUID NOT NULL, 
    scope VARCHAR(20) NOT NULL, 
    scope_id UUID, 
    provider VARCHAR(50) NOT NULL, 
    name VARCHAR(100) NOT NULL, 
    api_key_encrypted TEXT NOT NULL, 
    api_base VARCHAR(500), 
    extra JSONB, 
    is_active BOOLEAN DEFAULT 'true' NOT NULL, 
    legacy_user_provider_config_id UUID, 
    legacy_user_model_id UUID, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_provider_credentials_scope_name UNIQUE (scope, scope_id, provider, name)
);
CREATE INDEX ix_provider_credentials_scope ON provider_credentials (scope);
CREATE INDEX ix_provider_credentials_scope_id ON provider_credentials (scope_id);
CREATE INDEX ix_provider_credentials_provider ON provider_credentials (provider);
CREATE INDEX ix_provider_credentials_scope_lookup ON provider_credentials (scope, scope_id, provider);
INSERT INTO provider_credentials (
            id, scope, scope_id, provider, name, api_key_encrypted,
            api_base, is_active, legacy_user_provider_config_id,
            created_at, updated_at
        )
        SELECT
            gen_random_uuid(),
            'user',
            user_id,
            provider,
            COALESCE(provider, 'default'),
            api_key,
            api_base,
            is_active,
            id,
            COALESCE(created_at, now()),
            COALESCE(updated_at, now())
        FROM user_provider_configs
        WHERE NOT EXISTS (
            SELECT 1 FROM provider_credentials pc
            WHERE pc.legacy_user_provider_config_id = user_provider_configs.id
        );
INSERT INTO provider_credentials (
            id, scope, scope_id, provider, name, api_key_encrypted,
            api_base, is_active, legacy_user_model_id,
            created_at, updated_at
        )
        SELECT
            gen_random_uuid(),
            'user',
            user_id,
            provider,
            display_name,
            api_key_encrypted,
            api_base,
            is_active,
            id,
            COALESCE(created_at, now()),
            COALESCE(updated_at, now())
        FROM user_models
        WHERE api_key_encrypted IS NOT NULL
          AND user_id IS NOT NULL
          AND NOT EXISTS (
            SELECT 1 FROM provider_credentials pc
            WHERE pc.legacy_user_model_id = user_models.id
        );
