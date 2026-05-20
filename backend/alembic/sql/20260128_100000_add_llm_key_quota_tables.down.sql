-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260128_100000_add_llm_key_quota_tables.py
-- revision: g5h6i7j8k9l0
-- down_revision: f4g5h6i7j8k9
-- 方向: DOWNGRADE (down.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

DROP TABLE IF EXISTS quota_usage_logs;
DROP TABLE IF EXISTS user_quotas;
DROP TABLE IF EXISTS user_provider_configs;
