-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260513_unique_system_vkey_per_team.py
-- revision: 20260513_uvk
-- down_revision: 20260508_gw
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

WITH ranked AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    PARTITION BY team_id
                    ORDER BY created_at ASC, id ASC
                ) AS rn
            FROM gateway_virtual_keys
            WHERE is_system = TRUE
              AND is_active = TRUE
        )
        UPDATE gateway_virtual_keys gvk
        SET is_active = FALSE,
            updated_at = NOW()
        FROM ranked
        WHERE gvk.id = ranked.id
          AND ranked.rn > 1;
CREATE UNIQUE INDEX IF NOT EXISTS uq_gateway_virtual_keys_team_id_active_system
        ON gateway_virtual_keys (team_id)
        WHERE is_system = TRUE AND is_active = TRUE;
