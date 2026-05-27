-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260607_gateway_request_log_tenant_route_time.py
-- revision: 20260607_tenant_route
-- down_revision: 20260606_anon_tenant
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

CREATE INDEX ix_gateway_request_logs_tenant_route_time ON gateway_request_logs (tenant_id, route_name, created_at);
