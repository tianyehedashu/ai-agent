"""平台预算（``gateway_budgets``）写入校验（纯函数，不依赖 ORM/IO）。

成员+凭据(+模型) 维度仅允许配合 ``target_kind=user``；其余 target_kind 不得带 ``credential_id``。
凭据归属、模型别名归属等需 DB 的校验仍由 application 层 ``_assert_*`` 完成。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from libs.exceptions import ValidationError

from domains.gateway.domain.period_reset_anchor import (
    DEFAULT_PERIOD_RESET_ANCHOR,
    PeriodResetAnchor,
    normalize_period_reset_anchor,
)

if TYPE_CHECKING:
    import uuid

_ALLOWED_PERIODS = ("daily", "monthly", "total")


def validate_platform_period_reset_anchor(
    *,
    period: str,
    anchor: PeriodResetAnchor,
) -> None:
    """``total`` 禁止非默认锚点；``daily`` 忽略月切日由调用方归一化。"""
    if period == "total" and not anchor.is_default():
        raise ValidationError("总额周期不支持自定义日/月切时刻")
    if period == "daily" and anchor.day_of_month != DEFAULT_PERIOD_RESET_ANCHOR.day_of_month:
        raise ValidationError("每日周期不支持设置月切日")


def resolve_platform_period_reset_anchor(
    *,
    period: str,
    period_timezone: str | None,
    period_reset_minutes: int | None,
    period_reset_day: int | None,
) -> PeriodResetAnchor:
    day = 1 if period == "daily" else period_reset_day
    anchor = normalize_period_reset_anchor(
        timezone=period_timezone,
        time_minutes=period_reset_minutes,
        day_of_month=day,
    )
    validate_platform_period_reset_anchor(period=period, anchor=anchor)
    return anchor


def validate_platform_budget_upsert(
    *,
    target_kind: str,
    credential_id: uuid.UUID | None,
    model_name: str | None,
    period: str,
    limit_usd: object,
    limit_tokens: object,
    limit_requests: object,
    period_timezone: str | None = None,
    period_reset_minutes: int | None = None,
    period_reset_day: int | None = None,
) -> PeriodResetAnchor:
    """校验平台预算写入参数组合，非法时抛 :class:`ValidationError`。"""
    if period not in _ALLOWED_PERIODS:
        raise ValidationError(f"平台配额周期仅支持 {_ALLOWED_PERIODS}，收到: {period!r}")

    if credential_id is not None and target_kind != "user":
        raise ValidationError("credential_id 仅允许配合 target_kind=user 使用")

    if limit_usd is None and limit_tokens is None and limit_requests is None:
        raise ValidationError("配额需至少设置 limit_usd / limit_tokens / limit_requests 之一")

    return resolve_platform_period_reset_anchor(
        period=period,
        period_timezone=period_timezone,
        period_reset_minutes=period_reset_minutes,
        period_reset_day=period_reset_day,
    )


__all__ = [
    "resolve_platform_period_reset_anchor",
    "validate_platform_budget_upsert",
    "validate_platform_period_reset_anchor",
]
