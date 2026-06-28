"""配额周期重置锚点（IANA 时区 + 本地日/月切时刻）。

平台 ``gateway_budgets`` 与上下游 ``calendar_*`` 策略共用；纯函数，无 I/O。
短月语义对齐 Stripe Billing：当月无锚定日时落在当月最后一天。
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from libs.exceptions import ValidationError

DEFAULT_PERIOD_TIMEZONE: Final = "UTC"
DEFAULT_PERIOD_RESET_MINUTES: Final = 0
DEFAULT_PERIOD_RESET_DAY: Final = 1

PLATFORM_PERIOD_DAILY: Final = "daily"
PLATFORM_PERIOD_MONTHLY: Final = "monthly"
PLATFORM_PERIOD_TOTAL: Final = "total"

# ``total`` 周期固定哨兵，与 Redis ``:total`` 后缀语义一致。
PLATFORM_TOTAL_WINDOW_START: Final[datetime] = datetime(1970, 1, 1, tzinfo=UTC)


@dataclass(frozen=True)
class PeriodResetAnchor:
    """周期重置锚点（存储在规则行内，不参与唯一索引坐标）。"""

    timezone: str = DEFAULT_PERIOD_TIMEZONE
    time_minutes: int = DEFAULT_PERIOD_RESET_MINUTES
    day_of_month: int = DEFAULT_PERIOD_RESET_DAY

    def is_default(self) -> bool:
        return (
            self.timezone == DEFAULT_PERIOD_TIMEZONE
            and self.time_minutes == DEFAULT_PERIOD_RESET_MINUTES
            and self.day_of_month == DEFAULT_PERIOD_RESET_DAY
        )


DEFAULT_PERIOD_RESET_ANCHOR: Final[PeriodResetAnchor] = PeriodResetAnchor()


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _zone(tz_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError as exc:
        raise ValidationError(f"无效 IANA 时区: {tz_name!r}") from exc


def normalize_period_reset_anchor(
    *,
    timezone: str | None = None,
    time_minutes: int | None = None,
    day_of_month: int | None = None,
) -> PeriodResetAnchor:
    """归一化并校验锚点字段；``None`` 使用默认值。"""
    tz = (timezone or DEFAULT_PERIOD_TIMEZONE).strip() or DEFAULT_PERIOD_TIMEZONE
    _zone(tz)
    minutes = DEFAULT_PERIOD_RESET_MINUTES if time_minutes is None else time_minutes
    day = DEFAULT_PERIOD_RESET_DAY if day_of_month is None else day_of_month
    if not 0 <= minutes < 24 * 60:
        raise ValidationError(f"period_reset_minutes 须在 0..1439，收到: {minutes}")
    if not 1 <= day <= 31:
        raise ValidationError(f"period_reset_day 须在 1..31，收到: {day}")
    return PeriodResetAnchor(timezone=tz, time_minutes=minutes, day_of_month=day)


def period_reset_anchor_from_row(
    *,
    timezone: str | None,
    time_minutes: int | None,
    day_of_month: int | None,
) -> PeriodResetAnchor:
    """ORM 行读取：NULL 视为默认。"""
    return normalize_period_reset_anchor(
        timezone=timezone,
        time_minutes=time_minutes,
        day_of_month=day_of_month,
    )


def period_reset_anchor_from_plan_quota(
    *,
    reset_timezone: str | None,
    reset_time_minutes: int | None,
    reset_day_of_month: int | None,
) -> PeriodResetAnchor:
    """``provider_quotas`` / ``entitlement_plan_quotas`` 行 → 锚点。"""
    return normalize_period_reset_anchor(
        timezone=reset_timezone,
        time_minutes=reset_time_minutes,
        day_of_month=reset_day_of_month,
    )


def effective_day_in_month(year: int, month: int, day_of_month: int) -> int:
    """月末 clamp：``min(day_of_month, 当月最后一天)``。"""
    last_day = calendar.monthrange(year, month)[1]
    return min(day_of_month, last_day)


def _local_anchor_time(anchor: PeriodResetAnchor) -> tuple[int, int]:
    return divmod(anchor.time_minutes, 60)


def _local_datetime(
    year: int,
    month: int,
    day: int,
    anchor: PeriodResetAnchor,
) -> datetime:
    hour, minute = _local_anchor_time(anchor)
    tz = _zone(anchor.timezone)
    return datetime(year, month, day, hour, minute, tzinfo=tz)


def _calendar_daily_window_start_local(
    now: datetime,
    anchor: PeriodResetAnchor,
) -> datetime:
    """锚定时区下，包含 ``now`` 的日窗口起点（本地日切 + time_minutes）。"""
    when = _as_utc(now)
    tz = _zone(anchor.timezone)
    local = when.astimezone(tz)
    candidate = _local_datetime(local.year, local.month, local.day, anchor)
    if local < candidate:
        prev_day = local.date() - timedelta(days=1)
        return _local_datetime(prev_day.year, prev_day.month, prev_day.day, anchor)
    return candidate


def _calendar_monthly_window_start_local(
    now: datetime,
    anchor: PeriodResetAnchor,
) -> datetime:
    """锚定时区下，包含 ``now`` 的月窗口起点（day_of_month + 月末 clamp）。"""
    when = _as_utc(now)
    tz = _zone(anchor.timezone)
    local = when.astimezone(tz)
    eff_day = effective_day_in_month(local.year, local.month, anchor.day_of_month)
    candidate = _local_datetime(local.year, local.month, eff_day, anchor)
    if local < candidate:
        if local.month == 1:
            prev_year, prev_month = local.year - 1, 12
        else:
            prev_year, prev_month = local.year, local.month - 1
        prev_eff = effective_day_in_month(prev_year, prev_month, anchor.day_of_month)
        return _local_datetime(prev_year, prev_month, prev_eff, anchor)
    return candidate


def _calendar_daily_window_end_local(now: datetime, anchor: PeriodResetAnchor) -> datetime:
    start = _calendar_daily_window_start_local(now, anchor)
    tz = _zone(anchor.timezone)
    local_start = start.astimezone(tz)
    next_day = local_start.date() + timedelta(days=1)
    return _local_datetime(next_day.year, next_day.month, next_day.day, anchor)


def _calendar_monthly_window_end_local(now: datetime, anchor: PeriodResetAnchor) -> datetime:
    start = _calendar_monthly_window_start_local(now, anchor)
    tz = _zone(anchor.timezone)
    local_start = start.astimezone(tz)
    if local_start.month == 12:
        next_year, next_month = local_start.year + 1, 1
    else:
        next_year, next_month = local_start.year, local_start.month + 1
    next_eff = effective_day_in_month(next_year, next_month, anchor.day_of_month)
    return _local_datetime(next_year, next_month, next_eff, anchor)


def compute_period_window_start(
    now: datetime,
    period: str,
    anchor: PeriodResetAnchor | None = None,
) -> datetime:
    """按平台 ``period`` 与锚点计算当前窗口 ``window_start``（UTC）。"""
    resolved = anchor or DEFAULT_PERIOD_RESET_ANCHOR
    when = _as_utc(now)
    if period == PLATFORM_PERIOD_TOTAL:
        return PLATFORM_TOTAL_WINDOW_START
    if period == PLATFORM_PERIOD_DAILY:
        if resolved.is_default():
            return datetime(when.year, when.month, when.day, tzinfo=UTC)
        return _calendar_daily_window_start_local(when, resolved).astimezone(UTC)
    if period == PLATFORM_PERIOD_MONTHLY:
        if resolved.is_default():
            return datetime(when.year, when.month, 1, tzinfo=UTC)
        return _calendar_monthly_window_start_local(when, resolved).astimezone(UTC)
    raise ValidationError(f"未知平台配额周期: {period!r}")


def compute_period_reset_at(
    now: datetime,
    period: str,
    anchor: PeriodResetAnchor | None = None,
) -> datetime | None:
    """下次重置时刻（UTC）；``total`` 返回 ``None``。"""
    resolved = anchor or DEFAULT_PERIOD_RESET_ANCHOR
    when = _as_utc(now)
    if period == PLATFORM_PERIOD_TOTAL:
        return None
    if period == PLATFORM_PERIOD_DAILY:
        if resolved.is_default():
            return datetime(when.year, when.month, when.day, tzinfo=UTC) + timedelta(days=1)
        return _calendar_daily_window_end_local(when, resolved).astimezone(UTC)
    if period == PLATFORM_PERIOD_MONTHLY:
        if resolved.is_default():
            start = datetime(when.year, when.month, 1, tzinfo=UTC)
            if start.month == 12:
                return start.replace(year=start.year + 1, month=1)
            return start.replace(month=start.month + 1)
        return _calendar_monthly_window_end_local(when, resolved).astimezone(UTC)
    return None


def compute_platform_redis_period_suffix(
    now: datetime,
    period: str,
    anchor: PeriodResetAnchor | None = None,
) -> str:
    """平台 Redis 桶 period 后缀；默认锚点保持 ``%Y%m%d`` / ``%Y%m`` 兼容。"""
    resolved = anchor or DEFAULT_PERIOD_RESET_ANCHOR
    when = _as_utc(now)
    if period == PLATFORM_PERIOD_TOTAL:
        return "total"
    if period == PLATFORM_PERIOD_DAILY:
        if resolved.is_default():
            return when.strftime("%Y%m%d")
        window_start = compute_period_window_start(when, period, resolved)
        return f"ws:{int(window_start.timestamp())}"
    if period == PLATFORM_PERIOD_MONTHLY:
        if resolved.is_default():
            return when.strftime("%Y%m")
        window_start = compute_period_window_start(when, period, resolved)
        return f"ws:{int(window_start.timestamp())}"
    return "total"


__all__ = [
    "DEFAULT_PERIOD_RESET_ANCHOR",
    "DEFAULT_PERIOD_RESET_DAY",
    "DEFAULT_PERIOD_RESET_MINUTES",
    "DEFAULT_PERIOD_TIMEZONE",
    "PLATFORM_PERIOD_DAILY",
    "PLATFORM_PERIOD_MONTHLY",
    "PLATFORM_PERIOD_TOTAL",
    "PLATFORM_TOTAL_WINDOW_START",
    "PeriodResetAnchor",
    "compute_period_reset_at",
    "compute_period_window_start",
    "compute_platform_redis_period_suffix",
    "effective_day_in_month",
    "normalize_period_reset_anchor",
    "period_reset_anchor_from_plan_quota",
    "period_reset_anchor_from_row",
]
