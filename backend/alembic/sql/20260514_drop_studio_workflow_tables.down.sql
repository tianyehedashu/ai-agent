-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260514_drop_studio_workflow_tables.py
-- revision: 20260514_dsw
-- down_revision: 20260514_mtr
-- 方向: DOWNGRADE (down.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

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
