-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/009_add_agent_config_columns.py
-- revision: 009_add_agent_config_columns
-- down_revision: 008_add_langgraph_tables
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

ALTER TABLE agents ADD COLUMN temperature FLOAT DEFAULT '0.7' NOT NULL;
ALTER TABLE agents ADD COLUMN max_tokens INTEGER DEFAULT '4096' NOT NULL;
ALTER TABLE agents ADD COLUMN max_iterations INTEGER DEFAULT '20' NOT NULL;
ALTER TABLE agents ADD COLUMN is_public BOOLEAN DEFAULT 'false' NOT NULL;
ALTER TABLE agents ALTER COLUMN temperature DROP DEFAULT;
ALTER TABLE agents ALTER COLUMN max_tokens DROP DEFAULT;
ALTER TABLE agents ALTER COLUMN max_iterations DROP DEFAULT;
