-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/004_fix_timestamp_defaults.py
-- revision: 004
-- down_revision: 003
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

ALTER TABLE users
        ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP,
        ALTER COLUMN updated_at SET DEFAULT CURRENT_TIMESTAMP;;
ALTER TABLE agents
        ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP,
        ALTER COLUMN updated_at SET DEFAULT CURRENT_TIMESTAMP;;
ALTER TABLE sessions
        ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP,
        ALTER COLUMN updated_at SET DEFAULT CURRENT_TIMESTAMP;;
ALTER TABLE messages
        ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP;;
ALTER TABLE memories
        ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP,
        ALTER COLUMN updated_at SET DEFAULT CURRENT_TIMESTAMP;;
ALTER TABLE workflows
        ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP,
        ALTER COLUMN updated_at SET DEFAULT CURRENT_TIMESTAMP;;
ALTER TABLE workflow_versions
        ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP;;
