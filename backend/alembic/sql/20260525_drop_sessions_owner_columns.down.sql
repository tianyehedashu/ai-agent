-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260525_drop_sessions_owner_columns.py
-- revision: 20260525_dso
-- down_revision: 20260524_dau
-- 方向: DOWNGRADE (down.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

ALTER TABLE sessions ADD COLUMN user_id UUID;
ALTER TABLE sessions ADD COLUMN anonymous_user_id VARCHAR(100);
UPDATE sessions s
        SET user_id = t.owner_user_id
        FROM gateway_teams t
        WHERE s.tenant_id = t.id
          AND t.kind = 'personal'
          AND t.owner_user_id IS NOT NULL
          AND EXISTS (
              SELECT 1 FROM users u
              WHERE u.id = t.owner_user_id AND u.role <> 'anonymous'
          );
UPDATE sessions s
        SET user_id = NULL,
            anonymous_user_id = u.settings->>'anonymous_cookie_id'
        FROM gateway_teams t
        JOIN users u ON u.id = t.owner_user_id
        WHERE s.tenant_id = t.id
          AND t.kind = 'personal'
          AND u.role = 'anonymous'
          AND s.user_id IS NULL;
ALTER TABLE sessions ADD CONSTRAINT sessions_user_id_fkey FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE;
CREATE INDEX ix_sessions_user_id ON sessions (user_id);
CREATE INDEX ix_sessions_anonymous_user_id ON sessions (anonymous_user_id);
ALTER TABLE sessions ADD CONSTRAINT session_must_have_user_or_anonymous CHECK ((user_id IS NOT NULL) OR (anonymous_user_id IS NOT NULL));
ALTER TABLE sessions ALTER COLUMN tenant_id DROP NOT NULL;
