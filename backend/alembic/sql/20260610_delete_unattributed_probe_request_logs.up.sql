-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260610_delete_unattributed_probe_request_logs.py
-- revision: 20260610_del_probe_logs
-- down_revision: 20260609_giikin_uid
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

DELETE FROM gateway_request_logs
        WHERE user_id IS NULL
          AND credential_id IS NULL
          AND tenant_id IS NULL;
