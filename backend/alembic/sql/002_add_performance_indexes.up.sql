-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/002_add_performance_indexes.py
-- revision: 002
-- down_revision: 001_initial
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

CREATE INDEX idx_sessions_user_created ON sessions (user_id, created_at DESC);
CREATE INDEX idx_messages_session_created ON messages (session_id, created_at DESC);
CREATE INDEX idx_memories_user_type ON memories (user_id, memory_type);
CREATE INDEX idx_memories_user_importance ON memories (user_id, importance DESC, updated_at DESC);
CREATE INDEX idx_sessions_active
        ON sessions(user_id, created_at DESC)
        WHERE is_active = true;
CREATE INDEX idx_agents_config_gin
        ON agents USING GIN (config);
CREATE INDEX idx_sessions_metadata_gin
        ON sessions USING GIN (metadata);
