-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/005_add_session_status_and_context.py
-- revision: 005
-- down_revision: 004
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'sessions' AND column_name = 'status'
            ) THEN
                ALTER TABLE sessions ADD COLUMN status VARCHAR(20);
                UPDATE sessions SET status = CASE
                    WHEN is_active = true THEN 'active'
                    ELSE 'archived'
                END;
                ALTER TABLE sessions ALTER COLUMN status SET DEFAULT 'active';
                ALTER TABLE sessions ALTER COLUMN status SET NOT NULL;
            END IF;
        END $$;;
DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'sessions' AND column_name = 'metadata'
            ) THEN
                DROP INDEX IF EXISTS idx_sessions_metadata_gin;
                ALTER TABLE sessions RENAME COLUMN metadata TO context;
                ALTER TABLE sessions ALTER COLUMN context SET DEFAULT '{}'::jsonb;
                CREATE INDEX IF NOT EXISTS idx_sessions_context_gin ON sessions USING GIN (context);
            ELSIF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'sessions' AND column_name = 'context'
            ) THEN
                ALTER TABLE sessions ADD COLUMN context JSONB NOT NULL DEFAULT '{}'::jsonb;
                CREATE INDEX IF NOT EXISTS idx_sessions_context_gin ON sessions USING GIN (context);
            END IF;
        END $$;;
DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'sessions' AND column_name = 'message_count'
            ) THEN
                ALTER TABLE sessions ADD COLUMN message_count INTEGER;
                UPDATE sessions SET message_count = (
                    SELECT COUNT(*) FROM messages WHERE messages.session_id = sessions.id
                );
                ALTER TABLE sessions ALTER COLUMN message_count SET DEFAULT 0;
                ALTER TABLE sessions ALTER COLUMN message_count SET NOT NULL;
            END IF;
        END $$;;
DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'sessions' AND column_name = 'token_count'
            ) THEN
                ALTER TABLE sessions ADD COLUMN token_count INTEGER NOT NULL DEFAULT 0;
            END IF;
        END $$;;
DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'sessions' AND column_name = 'is_active'
            ) AND EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'sessions' AND column_name = 'status'
            ) THEN
                DROP INDEX IF EXISTS idx_sessions_active;
                ALTER TABLE sessions DROP COLUMN is_active;
            END IF;
        END $$;;
