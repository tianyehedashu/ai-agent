-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260224_add_user_models_table.py
-- revision: a3f8c2d1e4b7
-- down_revision: 20260224_phase
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

CREATE TABLE user_models (
    id UUID NOT NULL, 
    user_id UUID, 
    anonymous_user_id VARCHAR(100), 
    display_name VARCHAR(100) NOT NULL, 
    provider VARCHAR(50) NOT NULL, 
    model_id VARCHAR(200) NOT NULL, 
    api_key_encrypted TEXT, 
    api_base VARCHAR(500), 
    model_types VARCHAR(20)[] DEFAULT '{}' NOT NULL, 
    config JSONB, 
    is_active BOOLEAN DEFAULT 'true' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);
CREATE INDEX ix_user_models_user_id ON user_models (user_id);
CREATE INDEX ix_user_models_anonymous_user_id ON user_models (anonymous_user_id);
