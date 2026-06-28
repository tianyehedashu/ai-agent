"""Gateway 用量统计分页 response 组装。"""

from __future__ import annotations

from datetime import datetime

from domains.gateway.domain.usage.usage_read_model import UsageStatisticsGroupBy
from domains.gateway.presentation.schemas.common import (
    GatewayModelRouteUsageItem,
    GatewayModelUsageSummaryResponse,
    ManagedTeamModelRouteUsageItem,
    ManagedTeamModelUsageSummaryResponse,
    PlatformCredentialStatItem,
    PlatformCredentialStatListResponse,
    UsageStatisticsItemResponse,
    UsageStatisticsMetricResponse,
    UsageStatisticsResponse,
)
from libs.api.pagination import build_page


def build_usage_statistics_response(
    *,
    items: list[UsageStatisticsItemResponse],
    total: int,
    page: int,
    page_size: int,
    start: datetime,
    end: datetime,
    group_by: UsageStatisticsGroupBy,
    totals: UsageStatisticsMetricResponse,
) -> UsageStatisticsResponse:
    envelope = build_page(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )
    return UsageStatisticsResponse(
        **envelope.model_dump(),
        start=start,
        end=end,
        group_by=group_by,
        totals=totals,
    )


def build_gateway_model_usage_summary_response(
    *,
    items: list[GatewayModelRouteUsageItem],
    total: int,
    page: int,
    page_size: int,
    start: datetime,
    end: datetime,
) -> GatewayModelUsageSummaryResponse:
    envelope = build_page(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )
    return GatewayModelUsageSummaryResponse(
        **envelope.model_dump(),
        start=start,
        end=end,
    )


def build_managed_team_model_usage_summary_response(
    *,
    items: list[ManagedTeamModelRouteUsageItem],
    total: int,
    page: int,
    page_size: int,
    start: datetime,
    end: datetime,
) -> ManagedTeamModelUsageSummaryResponse:
    envelope = build_page(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )
    return ManagedTeamModelUsageSummaryResponse(
        **envelope.model_dump(),
        start=start,
        end=end,
    )


def build_platform_credential_stat_list_response(
    *,
    items: list[PlatformCredentialStatItem],
    total: int,
    page: int,
    page_size: int,
) -> PlatformCredentialStatListResponse:
    envelope = build_page(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )
    return PlatformCredentialStatListResponse(**envelope.model_dump())


__all__ = [
    "build_gateway_model_usage_summary_response",
    "build_managed_team_model_usage_summary_response",
    "build_platform_credential_stat_list_response",
    "build_usage_statistics_response",
]
