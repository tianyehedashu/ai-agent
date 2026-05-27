"""调用统计行内 breakdown 的入参校验（纯规则）。"""

from __future__ import annotations

from uuid import UUID

from domains.gateway.domain.usage_read_model import UsageStatisticsGroupBy
from libs.exceptions import ValidationError

_BREAKDOWN_BY_VALUES = frozenset(
    {
        UsageStatisticsGroupBy.CREDENTIAL,
        UsageStatisticsGroupBy.MODEL,
    }
)

_UUID_PARENT_GROUP_BY = frozenset(
    {
        UsageStatisticsGroupBy.CREDENTIAL,
        UsageStatisticsGroupBy.USER,
        UsageStatisticsGroupBy.TEAM,
        UsageStatisticsGroupBy.VKEY,
    }
)


def ensure_usage_statistics_breakdown_by(group_by: UsageStatisticsGroupBy) -> None:
    """breakdown 仅允许按凭据或模型二次分组。"""
    if group_by in _BREAKDOWN_BY_VALUES:
        return
    raise ValidationError(
        "breakdown_by must be credential or model",
        details={"field": "breakdown_by", "value": group_by},
    )


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


__all__ = [
    "ensure_usage_statistics_breakdown_by",
    "normalize_usage_statistics_parent_group_key",
]
