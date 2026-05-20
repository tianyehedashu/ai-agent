-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260514_gateway_log_deployment_dim.py
-- revision: 20260514_gld
-- down_revision: 20260514_grlc
-- 方向: DOWNGRADE (down.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

DROP INDEX ix_gateway_request_logs_deploy_team_time;
ALTER TABLE gateway_request_logs DROP COLUMN deployment_model_name;
ALTER TABLE gateway_request_logs DROP COLUMN deployment_gateway_model_id;
