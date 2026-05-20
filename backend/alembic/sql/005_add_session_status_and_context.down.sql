-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/005_add_session_status_and_context.py
-- revision: 005
-- down_revision: 004
-- 方向: DOWNGRADE (down.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'sessions' AND column_name = 'token_count'
            ) THEN
                ALTER TABLE sessions DROP COLUMN token_count;
            END IF;
        END $$;;
DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'sessions' AND column_name = 'message_count'
            ) THEN
                ALTER TABLE sessions DROP COLUMN message_count;
            END IF;
        END $$;;
DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'sessions' AND column_name = 'context'
            ) THEN
                ALTER TABLE sessions DROP COLUMN context;
            END IF;
        END $$;;
DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'sessions' AND column_name = 'is_active'
            ) THEN
                ALTER TABLE sessions ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT true;
                UPDATE sessions SET is_active = (status = 'active');
            END IF;
        END $$;;
DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'sessions' AND column_name = 'status'
            ) THEN
                ALTER TABLE sessions DROP COLUMN status;
            END IF;
        END $$;;
