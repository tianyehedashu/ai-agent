-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260127_160000_add_mcp_connection_status_and_tools.py
-- revision: a8b3c4d5e6f7
-- down_revision: d3f606546828
-- 方向: DOWNGRADE (down.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

ALTER TABLE mcp_servers DROP COLUMN available_tools;
ALTER TABLE mcp_servers DROP COLUMN last_error;
ALTER TABLE mcp_servers DROP COLUMN last_connected_at;
ALTER TABLE mcp_servers DROP COLUMN connection_status;
