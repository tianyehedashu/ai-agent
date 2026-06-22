"""调用统计行内 breakdown 的入参校验（纯规则）。"""

from __future__ import annotations

from uuid import UUID

from domains.gateway.domain.usage_read_model import (
    UsageStatisticsBreakdownBy,
    UsageStatisticsGroupBy,
)
from libs.api.pagination import MAX_PAGE_SIZE
from libs.exceptions import ValidationError

_UUID_PARENT_GROUP_BY = frozenset(
    {
        UsageStatisticsGroupBy.CREDENTIAL,
        UsageStatisticsGroupBy.USER,
        UsageStatisticsGroupBy.TEAM,
        UsageStatisticsGroupBy.VKEY,
    }
)


def breakdown_by_to_group_by(breakdown_by: UsageStatisticsBreakdownBy) -> UsageStatisticsGroupBy:
    """将 breakdown 维度映射为统计分组维度（同名字面量）。"""
    return UsageStatisticsGroupBy(breakdown_by.value)


def normalize_usage_statistics_parent_group_key(
    parent_group_by: UsageStatisticsGroupBy,
    parent_group_key: str,
) -> str:
    """校验并归一化父行 group_key；空串表示未关联（NULL）。"""
    key = parent_group_key.strip()
    if not key:
        return ""
    if parent_group_by not in _UUID_PARENT_GROUP_BY:
        return key
    try:
        UUID(key)
    except ValueError as exc:
        raise ValidationError(
            f"invalid parent_group_key for {parent_group_by}: {key!r}",
            details={"field": "parent_group_key", "parent_group_by": parent_group_by},
        ) from exc
    return key


def validate_breakdown_batch_parent_keys(parent_keys: list[str]) -> None:
    """批量 breakdown 父键数量不得超过单页统计上限（与 ``MAX_PAGE_SIZE`` 对齐）。"""
    if len(parent_keys) > MAX_PAGE_SIZE:
        raise ValidationError(
            f"parent_group_keys exceeds maximum of {MAX_PAGE_SIZE}",
            details={
                "field": "parent_group_keys",
                "max": MAX_PAGE_SIZE,
                "count": len(parent_keys),
            },
        )


__all__ = [
    "breakdown_by_to_group_by",
    "normalize_usage_statistics_parent_group_key",
    "validate_breakdown_batch_parent_keys",
]
