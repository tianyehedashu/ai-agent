-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260508_add_gateway_tables.py
-- revision: 20260508_gw
-- down_revision: 20260508_pc
-- 方向: DOWNGRADE (down.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

DROP TABLE gateway_alert_events;
DROP TABLE gateway_alert_rules;
DROP TABLE gateway_metrics_hourly;
DROP TABLE IF EXISTS gateway_request_logs CASCADE;
DROP TABLE gateway_budgets;
DROP TABLE gateway_routes;
DROP TABLE gateway_models;
DROP TABLE gateway_virtual_keys;
DROP TABLE gateway_team_members;
DROP TABLE gateway_teams;
