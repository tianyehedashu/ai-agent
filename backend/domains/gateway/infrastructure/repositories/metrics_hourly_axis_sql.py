"""UsageAxis → gateway_metrics_hourly WHERE 子句。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ColumnElement, and_, true

from domains.gateway.domain.usage.usage_axis import UsageAxis
from domains.gateway.infrastructure.models.metrics_hourly import GatewayMetricsHourly

if TYPE_CHECKING:
    from datetime import datetime


def metrics_hourly_axis_clauses(axis: UsageAxis) -> list[ColumnElement[bool]]:
    if axis.kind == "platform":
        return []
    if axis.kind == "workspace":
        if axis.team_id is None:
            raise ValueError("UsageAxis.workspace requires team_id")
        clauses: list[ColumnElement[bool]] = [
            GatewayMetricsHourly.tenant_id == axis.team_id
        ]
        if axis.member_user_id is not None:
            clauses.append(GatewayMetricsHourly.user_id == axis.member_user_id)
        return clauses
    if axis.kind == "user":
        if axis.user_id is None:
            raise ValueError("UsageAxis.user requires user_id")
        return [GatewayMetricsHourly.user_id == axis.user_id]
    raise ValueError(f"Unknown UsageAxis.kind: {axis.kind!r}")


def metrics_hourly_time_clauses(
    bucket_start: datetime,
    bucket_end_exclusive: datetime,
) -> list[ColumnElement[bool]]:
    return [
        GatewayMetricsHourly.bucket_at >= bucket_start,
        GatewayMetricsHourly.bucket_at < bucket_end_exclusive,
    ]


def metrics_hourly_and(*clauses: ColumnElement[bool]) -> ColumnElement[bool]:
    if not clauses:
        return true()
    return and_(*clauses)


__all__ = [
    "metrics_hourly_and",
    "metrics_hourly_axis_clauses",
    "metrics_hourly_time_clauses",
]
