"""上下游套餐配额周期锚点写入校验（纯函数）。"""

from __future__ import annotations

from libs.exceptions import ValidationError

from .period_reset_anchor import (
    DEFAULT_PERIOD_RESET_ANCHOR,
    PeriodResetAnchor,
    normalize_period_reset_anchor,
)
from .quota_plan import normalize_reset_strategy


def validate_plan_quota_reset_anchor(
    *,
    window_seconds: int,
    reset_strategy: str,
    anchor: PeriodResetAnchor,
) -> None:
    """``window_seconds=0`` / ``rolling`` 禁止非默认锚点。"""
    strategy = normalize_reset_strategy(reset_strategy)
    if window_seconds <= 0 and not anchor.is_default():
        raise ValidationError("套餐周期不支持自定义日/月切时刻")
    if strategy == "rolling" and not anchor.is_default():
        raise ValidationError(f"{strategy} 策略不支持自定义周期锚点")
    if strategy == "calendar_daily_utc" and anchor.day_of_month != DEFAULT_PERIOD_RESET_ANCHOR.day_of_month:
        raise ValidationError("每日日历周期不支持设置月切日")


def resolve_plan_quota_reset_anchor(
    *,
    window_seconds: int,
    reset_strategy: str,
    reset_timezone: str | None,
    reset_time_minutes: int | None,
    reset_day_of_month: int | None,
) -> PeriodResetAnchor:
    """归一化 plan quota 锚点并校验与 ``reset_strategy`` / ``window_seconds`` 一致。"""
    strategy = normalize_reset_strategy(reset_strategy)
    if window_seconds <= 0 or strategy == "rolling":
        anchor = DEFAULT_PERIOD_RESET_ANCHOR
        validate_plan_quota_reset_anchor(
            window_seconds=window_seconds,
            reset_strategy=strategy,
            anchor=anchor,
        )
        return anchor

    day = (
        DEFAULT_PERIOD_RESET_ANCHOR.day_of_month
        if strategy == "calendar_daily_utc"
        else reset_day_of_month
    )
    anchor = normalize_period_reset_anchor(
        timezone=reset_timezone,
        time_minutes=reset_time_minutes,
        day_of_month=day,
    )
    validate_plan_quota_reset_anchor(
        window_seconds=window_seconds,
        reset_strategy=strategy,
        anchor=anchor,
    )
    return anchor


__all__ = [
    "resolve_plan_quota_reset_anchor",
    "validate_plan_quota_reset_anchor",
]
