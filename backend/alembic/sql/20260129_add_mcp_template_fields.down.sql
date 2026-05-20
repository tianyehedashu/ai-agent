-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260129_add_mcp_template_fields.py
-- revision: h6i7j8k9l0m1
-- down_revision: g5h6i7j8k9l0
-- 方向: DOWNGRADE (down.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

DROP INDEX ix_mcp_servers_template_id;
ALTER TABLE mcp_servers DROP COLUMN inherit_defaults;
ALTER TABLE mcp_servers DROP COLUMN template_id;
