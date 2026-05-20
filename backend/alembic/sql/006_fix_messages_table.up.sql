-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/006_fix_messages_table.py
-- revision: 006
-- down_revision: 005
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'users' AND column_name = 'updated_at'
                ) THEN
                    ALTER TABLE users ADD COLUMN updated_at
                        TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP;
                END IF;
            END $$;;
DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'agents' AND column_name = 'updated_at'
                ) THEN
                    ALTER TABLE agents ADD COLUMN updated_at
                        TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP;
                END IF;
            END $$;;
DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'sessions' AND column_name = 'updated_at'
                ) THEN
                    ALTER TABLE sessions ADD COLUMN updated_at
                        TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP;
                END IF;
            END $$;;
DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'messages' AND column_name = 'updated_at'
                ) THEN
                    ALTER TABLE messages ADD COLUMN updated_at
                        TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP;
                END IF;
            END $$;;
DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'memories' AND column_name = 'updated_at'
                ) THEN
                    ALTER TABLE memories ADD COLUMN updated_at
                        TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP;
                END IF;
            END $$;;
DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'messages' AND column_name = 'token_count'
            ) THEN
                ALTER TABLE messages ADD COLUMN token_count INTEGER;
            END IF;
        END $$;;
