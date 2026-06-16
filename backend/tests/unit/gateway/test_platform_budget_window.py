"""``compute_platform_budget_window_start`` 单测。"""

from __future__ import annotations

from datetime import UTC, datetime

from domains.gateway.domain.platform_budget_window import (
    PLATFORM_TOTAL_WINDOW_START,
    compute_platform_budget_window_start,
)


def test_daily_window_is_utc_calendar_day_start() -> None:
    now = datetime(2026, 6, 15, 23, 59, 59, tzinfo=UTC)
    assert compute_platform_budget_window_start(now, "daily") == datetime(
        2026, 6, 15, 0, 0, tzinfo=UTC
    )


def test_monthly_window_is_utc_month_start() -> None:
    now = datetime(2026, 6, 15, 12, 0, tzinfo=UTC)
    assert compute_platform_budget_window_start(now, "monthly") == datetime(
        2026, 6, 1, 0, 0, tzinfo=UTC
    )


def test_total_window_uses_fixed_sentinel() -> None:
    now = datetime(2026, 6, 15, 12, 0, tzinfo=UTC)
    assert compute_platform_budget_window_start(now, "total") == PLATFORM_TOTAL_WINDOW_START


def test_naive_datetime_treated_as_utc() -> None:
    now = datetime(2026, 6, 16, 1, 0)  # noqa: DTZ001
    assert compute_platform_budget_window_start(now, "daily") == datetime(
        2026, 6, 16, 0, 0, tzinfo=UTC
    )
