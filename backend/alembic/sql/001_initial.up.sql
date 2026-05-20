-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/001_initial.py
-- revision: 001_initial
-- down_revision: base
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);
CREATE TABLE users (
    id UUID NOT NULL, 
    email VARCHAR(255) NOT NULL, 
    password_hash VARCHAR(255) NOT NULL, 
    name VARCHAR(100) NOT NULL, 
    avatar VARCHAR(500), 
    role VARCHAR(50) NOT NULL, 
    is_active BOOLEAN NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (email)
);
CREATE INDEX ix_users_email ON users (email);
CREATE TABLE agents (
    id UUID NOT NULL, 
    name VARCHAR(255) NOT NULL, 
    description TEXT, 
    user_id UUID NOT NULL, 
    model VARCHAR(100) NOT NULL, 
    system_prompt TEXT, 
    config JSONB NOT NULL, 
    tools JSONB NOT NULL, 
    is_active BOOLEAN NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);
CREATE INDEX ix_agents_user_id ON agents (user_id);
CREATE TABLE sessions (
    id UUID NOT NULL, 
    title VARCHAR(255), 
    user_id UUID NOT NULL, 
    agent_id UUID, 
    metadata JSONB NOT NULL, 
    is_active BOOLEAN NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    FOREIGN KEY(agent_id) REFERENCES agents (id) ON DELETE SET NULL
);
CREATE INDEX ix_sessions_user_id ON sessions (user_id);
CREATE INDEX ix_sessions_agent_id ON sessions (agent_id);
CREATE TABLE messages (
    id UUID NOT NULL, 
    session_id UUID NOT NULL, 
    role VARCHAR(50) NOT NULL, 
    content TEXT, 
    tool_calls JSONB, 
    tool_call_id VARCHAR(255), 
    metadata JSONB NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(session_id) REFERENCES sessions (id) ON DELETE CASCADE
);
CREATE INDEX ix_messages_session_id ON messages (session_id);
CREATE TABLE memories (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    content TEXT NOT NULL, 
    memory_type VARCHAR(50) NOT NULL, 
    importance INTEGER NOT NULL, 
    source_session_id UUID, 
    metadata JSONB NOT NULL, 
    access_count INTEGER NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);
CREATE INDEX ix_memories_user_id ON memories (user_id);
CREATE INDEX ix_memories_type ON memories (memory_type);
CREATE TABLE workflows (
    id UUID NOT NULL, 
    name VARCHAR(255) NOT NULL, 
    description TEXT, 
    user_id UUID NOT NULL, 
    code TEXT NOT NULL, 
    config JSONB NOT NULL, 
    is_published BOOLEAN NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);
CREATE INDEX ix_workflows_user_id ON workflows (user_id);
CREATE TABLE workflow_versions (
    id UUID NOT NULL, 
    workflow_id UUID NOT NULL, 
    version INTEGER NOT NULL, 
    code TEXT NOT NULL, 
    config JSONB NOT NULL, 
    message VARCHAR(500), 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(workflow_id) REFERENCES workflows (id) ON DELETE CASCADE
);
CREATE INDEX ix_workflow_versions_workflow_id ON workflow_versions (workflow_id);
INSERT INTO alembic_version (version_num) VALUES ('001_initial') RETURNING alembic_version.version_num;
