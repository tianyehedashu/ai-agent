-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260528_backfill_request_log_user.py
-- revision: 20260528_bfrlu
-- down_revision: 20260528_bfrlp2
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

UPDATE gateway_request_logs AS grl
    SET user_id = vk.created_by_user_id
    FROM gateway_virtual_keys AS vk
    WHERE grl.user_id IS NULL
      AND grl.vkey_id = vk.id
      AND vk.created_by_user_id IS NOT NULL
      AND vk.is_system = FALSE;
UPDATE gateway_request_logs AS grl
    SET user_id = u.id
    FROM users AS u
    WHERE grl.user_id IS NULL
      AND grl.user_email_snapshot IS NOT NULL
      AND u.email = grl.user_email_snapshot;
UPDATE gateway_request_logs AS grl
    SET user_id = gt.owner_user_id
    FROM gateway_teams AS gt
    WHERE grl.user_id IS NULL
      AND grl.tenant_id = gt.id
      AND gt.kind = 'personal';
