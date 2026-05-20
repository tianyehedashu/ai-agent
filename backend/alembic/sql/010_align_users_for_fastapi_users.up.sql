-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/010_align_users_for_fastapi_users.py
-- revision: 010_align_users
-- down_revision: 009_add_agent_config_columns
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

ALTER TABLE users ADD COLUMN hashed_password VARCHAR(255) DEFAULT '' NOT NULL;
ALTER TABLE users ADD COLUMN is_superuser BOOLEAN DEFAULT 'false' NOT NULL;
ALTER TABLE users ADD COLUMN is_verified BOOLEAN DEFAULT 'false' NOT NULL;
ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT 'true' NOT NULL;
CREATE UNIQUE INDEX ix_users_email ON users (email);
