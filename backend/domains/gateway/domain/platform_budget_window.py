"""Platform ``gateway_budgets`` 窗口起点（与 ``BudgetService`` Redis 桶日/月切分对齐）。"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Final

PLATFORM_PERIOD_DAILY: Final = "daily"
PLATFORM_PERIOD_MONTHLY: Final = "monthly"
PLATFORM_PERIOD_TOTAL: Final = "total"

# ``total`` 周期固定哨兵，与 Redis ``:total`` 后缀语义一致（累计全时段）。
PLATFORM_TOTAL_WINDOW_START: Final[datetime] = datetime(1970, 1, 1, tzinfo=UTC)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def compute_platform_budget_window_start(now: datetime, period: str) -> datetime:
    """按 ``gateway_budgets.period`` 计算当前窗口 ``window_start``（UTC 自然日/月或累计哨兵）。"""
    when = _as_utc(now)
    if period == PLATFORM_PERIOD_DAILY:
        return datetime(when.year, when.month, when.day, tzinfo=UTC)
    if period == PLATFORM_PERIOD_MONTHLY:
        return datetime(when.year, when.month, 1, tzinfo=UTC)
    return PLATFORM_TOTAL_WINDOW_START


__all__ = [
    "PLATFORM_PERIOD_DAILY",
    "PLATFORM_PERIOD_MONTHLY",
    "PLATFORM_PERIOD_TOTAL",
    "PLATFORM_TOTAL_WINDOW_START",
    "compute_platform_budget_window_start",
]
