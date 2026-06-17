"""plan_quota_reset_anchor_policy 单测。"""

from __future__ import annotations

from dataclasses import replace

import pytest

from domains.gateway.domain.period_reset_anchor import DEFAULT_PERIOD_RESET_ANCHOR
from domains.gateway.domain.policies.plan_quota_reset_anchor_policy import (
    resolve_plan_quota_reset_anchor,
    validate_plan_quota_reset_anchor,
)
from libs.exceptions import ValidationError


def test_rolling_rejects_non_default_anchor() -> None:
    with pytest.raises(ValidationError, match="rolling"):
        validate_plan_quota_reset_anchor(
            window_seconds=86400,
            reset_strategy="rolling",
            anchor=replace(DEFAULT_PERIOD_RESET_ANCHOR, timezone="Asia/Shanghai"),
        )


def test_resolve_rolling_returns_default_anchor() -> None:
    anchor = resolve_plan_quota_reset_anchor(
        window_seconds=86400,
        reset_strategy="rolling",
        reset_timezone="Asia/Shanghai",
        reset_time_minutes=540,
        reset_day_of_month=15,
    )
    assert anchor == DEFAULT_PERIOD_RESET_ANCHOR


def test_resolve_calendar_daily_uses_anchor_time() -> None:
    anchor = resolve_plan_quota_reset_anchor(
        window_seconds=86400,
        reset_strategy="calendar_daily_utc",
        reset_timezone="Asia/Shanghai",
        reset_time_minutes=540,
        reset_day_of_month=29,
    )
    assert anchor.timezone == "Asia/Shanghai"
    assert anchor.time_minutes == 540
    assert anchor.day_of_month == 1


def test_plan_period_rejects_custom_anchor() -> None:
    with pytest.raises(ValidationError, match="套餐周期"):
        validate_plan_quota_reset_anchor(
            window_seconds=0,
            reset_strategy="rolling",
            anchor=replace(DEFAULT_PERIOD_RESET_ANCHOR, timezone="Asia/Shanghai"),
        )
