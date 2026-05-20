-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260523_sessions_agents_tenant_id.py
-- revision: 20260523_sat
-- down_revision: 20260522_p3
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

ALTER TABLE sessions ADD COLUMN tenant_id UUID;
CREATE INDEX ix_sessions_tenant_id ON sessions (tenant_id);
UPDATE sessions s
        SET tenant_id = t.id
        FROM gateway_teams t
        WHERE s.user_id IS NOT NULL
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
ALTER TABLE agents ADD COLUMN tenant_id UUID;
CREATE INDEX ix_agents_tenant_id ON agents (tenant_id);
UPDATE agents a
        SET tenant_id = t.id
        FROM gateway_teams t
        WHERE t.owner_user_id = a.user_id
          AND t.kind = 'personal'
          AND t.is_active = TRUE;
ALTER TABLE agents ALTER COLUMN tenant_id SET NOT NULL;
