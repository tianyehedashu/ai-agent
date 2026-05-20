-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/011_add_anonymous_user_support.py
-- revision: 011
-- down_revision: 010_align_users
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

ALTER TABLE sessions ADD COLUMN anonymous_user_id VARCHAR(100);
CREATE INDEX ix_sessions_anonymous_user_id ON sessions (anonymous_user_id);
ALTER TABLE sessions ALTER COLUMN user_id DROP NOT NULL;
ALTER TABLE sessions ADD CONSTRAINT session_must_have_user_or_anonymous CHECK ((user_id IS NOT NULL) OR (anonymous_user_id IS NOT NULL));
