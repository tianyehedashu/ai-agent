-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260520_system_storage_config_single_active.py
-- revision: 20260520_ssc_uq
-- down_revision: 20260520_ssc
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

WITH ranked AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    ORDER BY created_at ASC, id ASC
                ) AS rn
            FROM system_storage_config
            WHERE is_active IS TRUE
        )
        UPDATE system_storage_config ssc
        SET is_active = FALSE,
            updated_at = NOW()
        FROM ranked
        WHERE ssc.id = ranked.id
          AND ranked.rn > 1;
CREATE UNIQUE INDEX IF NOT EXISTS uq_system_storage_config_single_active
        ON system_storage_config (is_active)
        WHERE is_active IS TRUE;
