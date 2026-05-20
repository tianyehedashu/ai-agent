-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/003_fix_user_schema.py
-- revision: 003
-- down_revision: 002
-- 方向: DOWNGRADE (down.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'users'
                AND column_name = 'name'
                AND is_nullable = 'YES'
            ) THEN
                ALTER TABLE users ALTER COLUMN name SET NOT NULL;
            END IF;
        END $$;;
DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'users' AND column_name = 'status'
            ) THEN
                ALTER TABLE users DROP COLUMN status;
            END IF;
        END $$;;
DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'users' AND column_name = 'settings'
            ) THEN
                ALTER TABLE users DROP COLUMN settings;
            END IF;
        END $$;;
DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'users' AND column_name = 'avatar_url'
            ) THEN
                ALTER TABLE users RENAME COLUMN avatar_url TO avatar;
            END IF;
        END $$;;
