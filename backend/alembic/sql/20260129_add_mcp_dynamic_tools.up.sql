-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260129_add_mcp_dynamic_tools.py
-- revision: p8q9r0s1t2u3
-- down_revision: h6i7j8k9l0m1
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

CREATE TABLE mcp_dynamic_tools (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    server_kind VARCHAR(30) NOT NULL, 
    server_id VARCHAR(100) NOT NULL, 
    tool_key VARCHAR(100) NOT NULL, 
    tool_type VARCHAR(50) NOT NULL, 
    config_json JSONB DEFAULT '{}'::jsonb NOT NULL, 
    description TEXT, 
    enabled BOOLEAN DEFAULT 'true' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id)
);
COMMENT ON COLUMN mcp_dynamic_tools.server_kind IS 'streamable_http | db_server';
COMMENT ON COLUMN mcp_dynamic_tools.server_id IS 'server_name or server UUID';
CREATE INDEX ix_mcp_dynamic_tools_server ON mcp_dynamic_tools (server_kind, server_id);
ALTER TABLE mcp_dynamic_tools ADD CONSTRAINT uq_mcp_dynamic_tools_server_tool UNIQUE (server_kind, server_id, tool_key);
