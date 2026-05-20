-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260514_gateway_log_credential_dim.py
-- revision: 20260514_grlc
-- down_revision: 20260514_gbm
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

ALTER TABLE gateway_request_logs ADD COLUMN credential_id UUID;
ALTER TABLE gateway_request_logs ADD COLUMN credential_name_snapshot VARCHAR(100);
CREATE INDEX ix_gateway_request_logs_credential_time ON gateway_request_logs (credential_id, created_at);
ALTER TABLE gateway_metrics_hourly ADD COLUMN credential_id UUID;
ALTER TABLE gateway_metrics_hourly DROP CONSTRAINT uq_gateway_metrics_hourly_dim;
ALTER TABLE gateway_metrics_hourly ADD CONSTRAINT uq_gateway_metrics_hourly_dim UNIQUE (bucket_at, team_id, user_id, vkey_id, credential_id, provider, real_model, capability);
