-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260519_drop_user_provider_configs.py
-- revision: 20260519_drop_upc
-- down_revision: 20260518_gmp
-- 方向: DOWNGRADE (down.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

CREATE TABLE user_provider_configs (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    user_id UUID NOT NULL, 
    provider VARCHAR(50) NOT NULL, 
    api_key TEXT NOT NULL, 
    api_base VARCHAR(255), 
    is_active BOOLEAN DEFAULT 'true' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_user_provider_config UNIQUE (user_id, provider)
);
CREATE INDEX ix_user_provider_configs_user_id ON user_provider_configs (user_id);
CREATE INDEX ix_user_provider_configs_provider ON user_provider_configs (provider);
CREATE INDEX ix_user_provider_configs_is_active ON user_provider_configs (is_active);
ALTER TABLE provider_credentials ADD COLUMN legacy_user_provider_config_id UUID;
COMMENT ON COLUMN provider_credentials.legacy_user_provider_config_id IS 'Ǩ���� user_provider_configs ��Դ��¼ ID';
