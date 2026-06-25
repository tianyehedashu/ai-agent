-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260701_gateway_resource_grants.py
-- revision: 20260701_grg
-- down_revision: 20260630_socp
-- 方向: DOWNGRADE (down.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

DROP INDEX IF EXISTS ix_gateway_request_logs_resource_owner_time;
ALTER TABLE gateway_metrics_hourly DROP COLUMN resource_owner_user_id;
ALTER TABLE gateway_request_logs DROP COLUMN resource_owner_user_id;
DROP INDEX IF EXISTS ix_gateway_resource_grants_target_enabled;
DROP INDEX ix_gateway_resource_grants_subject;
DROP INDEX ix_gateway_resource_grants_owner_user_id;
DROP TABLE gateway_resource_grants;
