-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260129_add_mcp_dynamic_prompts.py
-- revision: q9r0s1t2u3v4
-- down_revision: p8q9r0s1t2u3
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

CREATE TABLE mcp_dynamic_prompts (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    server_kind VARCHAR(30) NOT NULL, 
    server_id VARCHAR(100) NOT NULL, 
    prompt_key VARCHAR(100) NOT NULL, 
    title VARCHAR(200), 
    description TEXT, 
    arguments_schema JSONB DEFAULT '[]'::jsonb NOT NULL, 
    template TEXT NOT NULL, 
    enabled BOOLEAN DEFAULT 'true' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id)
);
COMMENT ON COLUMN mcp_dynamic_prompts.server_kind IS 'streamable_http | db_server';
COMMENT ON COLUMN mcp_dynamic_prompts.server_id IS 'server_name or server UUID';
COMMENT ON COLUMN mcp_dynamic_prompts.arguments_schema IS '[{"name":"x","description":"...","required":true}]';
CREATE INDEX ix_mcp_dynamic_prompts_server ON mcp_dynamic_prompts (server_kind, server_id);
ALTER TABLE mcp_dynamic_prompts ADD CONSTRAINT uq_mcp_dynamic_prompts_server_prompt UNIQUE (server_kind, server_id, prompt_key);
