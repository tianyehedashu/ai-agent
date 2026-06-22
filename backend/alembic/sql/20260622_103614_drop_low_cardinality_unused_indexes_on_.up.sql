-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260622_103614_drop_low_cardinality_unused_indexes_on_.py
-- revision: 8418cdb1fed7
-- down_revision: 20260628_fpq
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

DROP INDEX IF EXISTS ix_gateway_request_logs_capability;
DROP INDEX IF EXISTS ix_gateway_request_logs_client_type;
