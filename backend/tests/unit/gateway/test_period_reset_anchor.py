"""``period_reset_anchor`` 单测：日/月切、月末 clamp、默认锚点兼容。"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from domains.gateway.domain.period_reset_anchor import (
    DEFAULT_PERIOD_RESET_ANCHOR,
    PeriodResetAnchor,
    compute_period_reset_at,
    compute_period_window_start,
    compute_platform_redis_period_suffix,
    effective_day_in_month,
    normalize_period_reset_anchor,
)
from libs.exceptions import ValidationError


def test_effective_day_clamps_short_months() -> None:
    assert effective_day_in_month(2026, 2, 29) == 28
    assert effective_day_in_month(2024, 2, 29) == 29
    assert effective_day_in_month(2026, 4, 31) == 30
    assert effective_day_in_month(2026, 1, 31) == 31


def test_default_anchor_matches_utc_natural_day() -> None:
    now = datetime(2026, 6, 15, 10, 30, tzinfo=UTC)
    assert compute_period_window_start(now, "daily") == datetime(2026, 6, 15, tzinfo=UTC)
    assert compute_period_window_start(now, "monthly") == datetime(2026, 6, 1, tzinfo=UTC)
    assert compute_platform_redis_period_suffix(now, "daily") == "20260615"
    assert compute_platform_redis_period_suffix(now, "monthly") == "202606"


def test_custom_daily_anchor_asia_shanghai() -> None:
    anchor = PeriodResetAnchor(timezone="Asia/Shanghai", time_minutes=9 * 60, day_of_month=1)
    # 2026-06-15 00:30 UTC = 08:30 Shanghai → still previous window (started 6/14 09:00)
    before_cut = datetime(2026, 6, 14, 16, 30, tzinfo=UTC)
    assert compute_period_window_start(before_cut, "daily", anchor) == datetime(
        2026, 6, 14, 1, 0, tzinfo=UTC
    )
    after_cut = datetime(2026, 6, 14, 17, 0, tzinfo=UTC)
    assert compute_period_window_start(after_cut, "daily", anchor) == datetime(
        2026, 6, 14, 1, 0, tzinfo=UTC
    )


def test_custom_monthly_day_29_february() -> None:
    anchor = PeriodResetAnchor(timezone="UTC", time_minutes=0, day_of_month=29)
    # 2026-03-01 → window started 2026-02-28 00:00 UTC (clamp)
    now = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
    assert compute_period_window_start(now, "monthly", anchor) == datetime(
        2026, 2, 28, 0, 0, tzinfo=UTC
    )
    reset_at = compute_period_reset_at(now, "monthly", anchor)
    assert reset_at == datetime(2026, 3, 29, 0, 0, tzinfo=UTC)


def test_custom_monthly_day_31_april() -> None:
    anchor = PeriodResetAnchor(timezone="UTC", time_minutes=0, day_of_month=31)
    now = datetime(2026, 4, 15, tzinfo=UTC)
    assert compute_period_window_start(now, "monthly", anchor) == datetime(
        2026, 3, 31, 0, 0, tzinfo=UTC
    )
    now_may = datetime(2026, 5, 1, tzinfo=UTC)
    assert compute_period_window_start(now_may, "monthly", anchor) == datetime(
        2026, 4, 30, 0, 0, tzinfo=UTC
    )


def test_non_default_anchor_redis_suffix() -> None:
    anchor = PeriodResetAnchor(timezone="Asia/Shanghai", time_minutes=540, day_of_month=1)
    now = datetime(2026, 6, 15, 10, 0, tzinfo=UTC)
    suffix = compute_platform_redis_period_suffix(now, "daily", anchor)
    assert suffix.startswith("ws:")
    window = compute_period_window_start(now, "daily", anchor)
    assert suffix == f"ws:{int(window.timestamp())}"


def test_normalize_rejects_invalid() -> None:
    with pytest.raises(ValidationError):
        normalize_period_reset_anchor(timezone="Not/AZone")
    with pytest.raises(ValidationError):
        normalize_period_reset_anchor(day_of_month=32)
    with pytest.raises(ValidationError):
        normalize_period_reset_anchor(time_minutes=1500)


def test_default_anchor_is_default() -> None:
    assert DEFAULT_PERIOD_RESET_ANCHOR.is_default()
