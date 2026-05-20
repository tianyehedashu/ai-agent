-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260514_gateway_log_deployment_dim.py
-- revision: 20260514_gld
-- down_revision: 20260514_grlc
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

ALTER TABLE gateway_request_logs ADD COLUMN deployment_gateway_model_id UUID;
ALTER TABLE gateway_request_logs ADD COLUMN deployment_model_name VARCHAR(200);
CREATE INDEX ix_gateway_request_logs_deploy_team_time ON gateway_request_logs (team_id, deployment_gateway_model_id, created_at);
