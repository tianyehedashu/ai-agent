-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260525_drop_sessions_owner_columns.py
-- revision: 20260525_dso
-- down_revision: 20260524_dau
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

UPDATE sessions s
        SET tenant_id = t.id
        FROM gateway_teams t
        WHERE s.user_id IS NOT NULL
          AND s.tenant_id IS NULL
          AND t.owner_user_id = s.user_id
          AND t.kind = 'personal'
          AND t.is_active = TRUE;
UPDATE sessions s
        SET tenant_id = t.id
        FROM users u
        JOIN gateway_teams t ON t.owner_user_id = u.id
            AND t.kind = 'personal'
            AND t.is_active = TRUE
        WHERE s.anonymous_user_id IS NOT NULL
          AND s.tenant_id IS NULL
          AND u.role = 'anonymous'
          AND u.settings->>'anonymous_cookie_id' = s.anonymous_user_id;
INSERT INTO gateway_teams (
            id, name, slug, kind, owner_user_id, settings, is_active, created_at, updated_at
        )
        SELECT
            gen_random_uuid(),
            'Personal',
            'personal-' || u.user_id::text,
            'personal',
            u.user_id,
            '{}'::jsonb,
            TRUE,
            NOW(),
            NOW()
        FROM (SELECT DISTINCT user_id FROM sessions WHERE tenant_id IS NULL AND user_id IS NOT NULL) u
        WHERE NOT EXISTS (
            SELECT 1 FROM gateway_teams t
            WHERE t.owner_user_id = u.user_id AND t.kind = 'personal' AND t.is_active = TRUE
        );
INSERT INTO gateway_team_members (id, team_id, user_id, role, created_at, updated_at)
        SELECT gen_random_uuid(), t.id, t.owner_user_id, 'owner', NOW(), NOW()
        FROM gateway_teams t
        WHERE t.kind = 'personal'
          AND NOT EXISTS (
              SELECT 1 FROM gateway_team_members m
              WHERE m.team_id = t.id AND m.user_id = t.owner_user_id
          );
UPDATE sessions s
        SET tenant_id = t.id
        FROM gateway_teams t
        WHERE s.tenant_id IS NULL
          AND s.user_id IS NOT NULL
          AND t.owner_user_id = s.user_id
          AND t.kind = 'personal'
          AND t.is_active = TRUE;
DELETE FROM sessions WHERE tenant_id IS NULL;
ALTER TABLE sessions ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE sessions DROP CONSTRAINT session_must_have_user_or_anonymous;
DROP INDEX ix_sessions_anonymous_user_id;
DROP INDEX ix_sessions_user_id;
ALTER TABLE sessions DROP CONSTRAINT sessions_user_id_fkey;
ALTER TABLE sessions DROP COLUMN anonymous_user_id;
ALTER TABLE sessions DROP COLUMN user_id;
