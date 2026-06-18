-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/20260626_migrate_rolling_window_to_calendar.py
-- revision: 20260626_r2c
-- down_revision: 20260625_pra
-- 方向: UPGRADE (up.sql)
--   up.sql   = 升级（从 down_revision 升到 revision）
--   down.sql = 回滚（从 revision 退回到 down_revision）
-- 执行后请手工维护 alembic_version.version_num
-- =============================================================================

UPDATE provider_plan_quotas
                SET reset_strategy = 'calendar_daily_utc',
                    reset_timezone = 'UTC',
                    reset_time_minutes = 0,
                    reset_day_of_month = 1
                WHERE reset_strategy = 'rolling'
                  AND window_seconds = 86400;
UPDATE provider_plan_quotas
                SET reset_strategy = 'calendar_monthly_utc',
                    reset_timezone = 'UTC',
                    reset_time_minutes = 0,
                    reset_day_of_month = 1
                WHERE reset_strategy = 'rolling'
                  AND window_seconds = 2592000;
UPDATE entitlement_plan_quotas
                SET reset_strategy = 'calendar_daily_utc',
                    reset_timezone = 'UTC',
                    reset_time_minutes = 0,
                    reset_day_of_month = 1
                WHERE reset_strategy = 'rolling'
                  AND window_seconds = 86400;
UPDATE entitlement_plan_quotas
                SET reset_strategy = 'calendar_monthly_utc',
                    reset_timezone = 'UTC',
                    reset_time_minutes = 0,
                    reset_day_of_month = 1
                WHERE reset_strategy = 'rolling'
                  AND window_seconds = 2592000;
