-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260520_gateway_request_log_client.py
-- revision: 20260520_grlc
-- down_revision: 20260519_drop_upc
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

ALTER TABLE gateway_request_logs ADD COLUMN client_type VARCHAR(32);
ALTER TABLE gateway_request_logs ADD COLUMN client_ua VARCHAR(512);
CREATE INDEX ix_gateway_request_logs_client_type ON gateway_request_logs (client_type);
