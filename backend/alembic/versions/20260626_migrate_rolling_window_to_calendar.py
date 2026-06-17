"""gateway plan quotas: migrate rolling 24h/30d windows to calendar reset

Revision ID: 20260626_r2c
Revises: 20260625_pra
Create Date: 2026-06-26

历史上下游套餐配额在未显式指定策略时默认落 ``rolling``，导致「每日 / 每月」窗口被当成
滑动窗口（无固定重置、起点随时间漂移、展示读偶发低估）。本迁移把日/月窗口的 rolling 规则
归一为固定日历重置（默认锚点 UTC 00:00 / 每月 1 号），与写路径新默认
``default_reset_strategy_for_window`` 对齐。子日 / 自定义秒数窗口仍保留 rolling。

锚点统一落系统默认（UTC 00:00），用户可在配额表单中按需改时区 / 时刻 / 月切日。
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260626_r2c"
down_revision: str | None = "20260625_pra"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PLAN_QUOTA_TABLES = ("provider_plan_quotas", "entitlement_plan_quotas")

# window_seconds → 目标固定日历策略（与 default_reset_strategy_for_window 一致）。
_WINDOW_TO_STRATEGY = {
    86400: "calendar_daily_utc",
    2592000: "calendar_monthly_utc",
}


def upgrade() -> None:
    for table in _PLAN_QUOTA_TABLES:
        for window_seconds, strategy in _WINDOW_TO_STRATEGY.items():
            op.execute(
                f"""
                UPDATE {table}
                SET reset_strategy = '{strategy}',
                    reset_timezone = 'UTC',
                    reset_time_minutes = 0,
                    reset_day_of_month = 1
                WHERE reset_strategy = 'rolling'
                  AND window_seconds = {window_seconds}
                """
            )


def downgrade() -> None:
    # 数据归一迁移：无法区分「本次迁移转换的」与「用户主动配置的」日历规则，
    # 回退会误伤后者，故 downgrade 不做反向改写。
    pass
