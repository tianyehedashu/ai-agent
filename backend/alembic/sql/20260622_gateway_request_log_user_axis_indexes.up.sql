-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260622_gateway_request_log_user_axis_indexes.py
-- revision: 20260622_grl_user_ix
-- down_revision: 20260622_btcc
-- 方向: UPGRADE (up.sql)
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

CREATE INDEX IF NOT EXISTS ix_gateway_request_logs_user_platform_inbound
    ON gateway_request_logs (user_id, created_at)
    WHERE vkey_id IS NULL;

CREATE INDEX IF NOT EXISTS ix_gateway_request_logs_vkey_time_notnull
    ON gateway_request_logs (vkey_id, created_at)
    WHERE vkey_id IS NOT NULL;
