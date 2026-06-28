"""Platform ``gateway_budgets`` 窗口起点（与 ``BudgetService`` Redis 桶日/月切分对齐）。"""

from __future__ import annotations

from datetime import datetime

from domains.gateway.domain.quota.period_reset_anchor import (
    DEFAULT_PERIOD_RESET_ANCHOR,
    PLATFORM_PERIOD_DAILY,
    PLATFORM_PERIOD_MONTHLY,
    PLATFORM_PERIOD_TOTAL,
    PLATFORM_TOTAL_WINDOW_START,
    PeriodResetAnchor,
    compute_period_window_start,
)

__all__ = [
    "PLATFORM_PERIOD_DAILY",
    "PLATFORM_PERIOD_MONTHLY",
    "PLATFORM_PERIOD_TOTAL",
    "PLATFORM_TOTAL_WINDOW_START",
    "compute_platform_budget_window_start",
]


def compute_platform_budget_window_start(
    now: datetime,
    period: str,
    anchor: PeriodResetAnchor | None = None,
) -> datetime:
    """按 ``gateway_budgets.period`` 与可选锚点计算当前窗口 ``window_start``（UTC）。"""
    return compute_period_window_start(
        now,
        period,
        anchor or DEFAULT_PERIOD_RESET_ANCHOR,
    )
