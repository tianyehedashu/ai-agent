"""平台预算（``gateway_budgets``）写入校验（纯函数，不依赖 ORM/IO）。

成员+凭据(+模型) 维度仅允许配合 ``target_kind=user``；其余 target_kind 不得带 ``credential_id``。
凭据归属、模型别名归属等需 DB 的校验仍由 application 层 ``_assert_*`` 完成。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from libs.exceptions import ValidationError

if TYPE_CHECKING:
    import uuid

_ALLOWED_PERIODS = ("daily", "monthly", "total")


def validate_platform_budget_upsert(
    *,
    target_kind: str,
    credential_id: uuid.UUID | None,
    model_name: str | None,
    period: str,
    limit_usd: object,
    limit_tokens: object,
    limit_requests: object,
) -> None:
    """校验平台预算写入参数组合，非法时抛 :class:`ValidationError`。"""
    if period not in _ALLOWED_PERIODS:
        raise ValidationError(f"平台配额周期仅支持 {_ALLOWED_PERIODS}，收到: {period!r}")

    if credential_id is not None and target_kind != "user":
        raise ValidationError("credential_id 仅允许配合 target_kind=user 使用")

    if limit_usd is None and limit_tokens is None and limit_requests is None:
        raise ValidationError("配额需至少设置 limit_usd / limit_tokens / limit_requests 之一")

    # credential_id 为空时 model_name 仍可单独使用（成员+模型汇总行，历史行为）；
    # credential_id 非空且 model_name 为空表示该凭据下全模型限额，允许。


__all__ = ["validate_platform_budget_upsert"]
