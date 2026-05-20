-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260127_150000_add_mcp_servers.py
-- revision: d3f606546828
-- down_revision: 5783302b5009
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

CREATE TABLE mcp_servers (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    user_id UUID, 
    name VARCHAR(100) NOT NULL, 
    display_name VARCHAR(200), 
    url VARCHAR(500) NOT NULL, 
    scope VARCHAR(20) DEFAULT 'user' NOT NULL, 
    env_type VARCHAR(50) NOT NULL, 
    env_config JSONB DEFAULT '{}'::jsonb NOT NULL, 
    enabled BOOLEAN DEFAULT 'true' NOT NULL, 
    description TEXT, 
    category VARCHAR(50), 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (name)
);
CREATE INDEX ix_mcp_servers_user_id ON mcp_servers (user_id);
CREATE INDEX ix_mcp_servers_name ON mcp_servers (name);
COMMENT ON COLUMN mcp_servers.user_id IS '�������û�ID��NULL��ʾϵͳ��������';
INSERT INTO mcp_servers (name, display_name, url, scope, env_type, env_config, enabled, description, category)
            VALUES
                ('filesystem', '�ļ�ϵͳ', 'stdio://npx -y @modelcontextprotocol/server-filesystem', 'system', 'preinstalled', '{"allowedDirectories": ["."]}'::jsonb, true, '���ʱ����ļ�ϵͳ', 'productivity'),
                ('github', 'GitHub', 'stdio://npx -y @modelcontextprotocol/server-github', 'system', 'dynamic_injected', '{}'::jsonb, false, 'GitHub �ֿ⼯�ɣ���Ҫ���� token��', 'development'),
                ('postgres', 'PostgreSQL', 'stdio://npx -y @modelcontextprotocol/server-postgres', 'system', 'dynamic_injected', '{"connectionString": ""}'::jsonb, false, 'PostgreSQL ���ݿ����', 'database'),
                ('slack', 'Slack', 'stdio://npx -y @modelcontextprotocol/server-slack', 'system', 'dynamic_injected', '{}'::jsonb, false, 'Slack ���ɣ���Ҫ���� token��', 'communication'),
                ('brave-search', 'Brave ����', 'stdio://npx -y @modelcontextprotocol/server-brave-search', 'system', 'preinstalled', '{}'::jsonb, true, 'Brave ��ҳ����', 'search');;
