-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260615_gateway_budget_tenant_backfill.py
-- revision: 20260615_gbtb
-- down_revision: 20260614_oaipfx
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

WITH picked AS (
    SELECT DISTINCT ON (m.user_id)
        m.user_id,
        m.team_id
    FROM gateway_team_members m
    JOIN gateway_teams t ON t.id = m.team_id
    WHERE t.is_active IS TRUE
    ORDER BY m.user_id, (t.kind = 'shared') DESC, m.created_at ASC, m.team_id
)
        DELETE FROM gateway_budgets b
        USING picked p
        WHERE b.target_kind = 'user'
          AND b.credential_id IS NULL
          AND b.tenant_id IS NULL
          AND b.target_id = p.user_id
          AND EXISTS (
              SELECT 1 FROM gateway_budgets x
              WHERE x.target_kind = 'user'
                AND x.target_id = b.target_id
                AND x.credential_id IS NULL
                AND x.tenant_id = p.team_id
                AND x.period = b.period
                AND x.model_name IS NOT DISTINCT FROM b.model_name
          );
WITH picked AS (
    SELECT DISTINCT ON (m.user_id)
        m.user_id,
        m.team_id
    FROM gateway_team_members m
    JOIN gateway_teams t ON t.id = m.team_id
    WHERE t.is_active IS TRUE
    ORDER BY m.user_id, (t.kind = 'shared') DESC, m.created_at ASC, m.team_id
)
        UPDATE gateway_budgets b
        SET tenant_id = p.team_id
        FROM picked p
        WHERE b.target_kind = 'user'
          AND b.credential_id IS NULL
          AND b.tenant_id IS NULL
          AND b.target_id = p.user_id;
