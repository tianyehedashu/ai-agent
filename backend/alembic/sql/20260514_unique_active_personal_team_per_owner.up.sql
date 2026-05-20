-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260514_unique_active_personal_team_per_owner.py
-- revision: 20260514_upt
-- down_revision: 20260513_uvk
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

WITH ranked AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    PARTITION BY owner_user_id
                    ORDER BY created_at ASC, id ASC
                ) AS rn
            FROM gateway_teams
            WHERE kind = 'personal'
              AND is_active IS TRUE
        )
        UPDATE gateway_teams gt
        SET is_active = FALSE,
            updated_at = NOW()
        FROM ranked
        WHERE gt.id = ranked.id
          AND ranked.rn > 1;
CREATE UNIQUE INDEX IF NOT EXISTS uq_gateway_teams_owner_personal_active
        ON gateway_teams (owner_user_id)
        WHERE kind = 'personal' AND is_active IS TRUE;
