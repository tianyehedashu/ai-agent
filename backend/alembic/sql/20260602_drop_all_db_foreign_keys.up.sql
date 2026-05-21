-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260602_drop_all_db_foreign_keys.py
-- revision: 20260602_dafk
-- down_revision: 20260601_dltif
-- 方向: UPGRADE (up.sql)
-- =============================================================================

DO $drop_all_public_fks$
DECLARE
    r RECORD;
BEGIN
    FOR r IN
        SELECT n.nspname AS schemaname, t.relname AS tablename, c.conname AS conname
        FROM pg_constraint c
        JOIN pg_class t ON c.conrelid = t.oid
        JOIN pg_namespace n ON t.relnamespace = n.oid
        WHERE c.contype = 'f'
          AND n.nspname = 'public'
    LOOP
        EXECUTE format(
            'ALTER TABLE %I.%I DROP CONSTRAINT IF EXISTS %I',
            r.schemaname,
            r.tablename,
            r.conname
        );
    END LOOP;
END $drop_all_public_fks$;
