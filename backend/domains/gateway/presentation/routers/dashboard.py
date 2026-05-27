"""Dashboard 子 router (含 /dashboard/summary 与 /dashboard/margin)。

Stage 2 起：``aggregate_request_log_summary`` 经 ``UsageAxis`` 统一访问仓储。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Annotated
import uuid

from fastapi import APIRouter, Depends, Query

from domains.gateway.application.management.usage_reads import (
    UsageStatisticsBreakdownSummary,
    UsageStatisticsItem,
    UsageStatisticsMetric,
)
from domains.gateway.domain.margin_read_model import MarginGroupBy
from domains.gateway.domain.policies.pricing_visibility import (
    can_view_margin_dashboard,
    can_view_pricing_cost_fields,
)
from domains.gateway.domain.usage_read_model import (
    USAGE_AGGREGATION_QUERY_DESCRIPTION,
    UsageAggregation,
    UsageStatisticsBreakdownBy,
    UsageStatisticsFilters,
    UsageStatisticsGroupBy,
)
from domains.gateway.presentation.deps import CurrentTeam
from domains.gateway.presentation.gateway_usage_list_response import (
    build_usage_statistics_response,
)
from domains.gateway.presentation.schemas.common import (
    DashboardClientTypeBreakdown,
    DashboardSummaryResponse,
    MarginGroupItemResponse,
    MarginSummaryResponse,
    UsageStatisticsBreakdownResponse,
    UsageStatisticsBreakdownSliceResponse,
    UsageStatisticsItemResponse,
    UsageStatisticsMetricResponse,
    UsageStatisticsResponse,
)
from libs.api.pagination import PageParams, page_query_params
from libs.exceptions import PermissionDeniedError

from ._common import MgmtReads

router = APIRouter()
PageDep = Annotated[PageParams, Depends(page_query_params)]


def _usage_stats_metric_response(
    metric: UsageStatisticsMetric,
    *,
    show_cost: bool,
) -> UsageStatisticsMetricResponse:
    return UsageStatisticsMetricResponse(
        requests=metric.requests,
        success_count=metric.success_count,
        failure_count=metric.failure_count,
        input_tokens=metric.input_tokens,
        output_tokens=metric.output_tokens,
        cached_tokens=metric.cached_tokens,
        total_tokens=metric.total_tokens,
        cost_usd=metric.cost_usd if show_cost else Decimal("0"),
        avg_latency_ms=metric.avg_latency_ms,
        cache_hit_count=metric.cache_hit_count,
        success_rate=metric.success_rate,
        cache_hit_rate=metric.cache_hit_rate,
    )


def _usage_statistics_item_response(
    item: UsageStatisticsItem,
    *,
    show_cost: bool,
) -> UsageStatisticsItemResponse:
    metric = _usage_stats_metric_response(item, show_cost=show_cost)
    return UsageStatisticsItemResponse(
        group_key=item.group_key,
        label=item.label,
        requests=metric.requests,
        success_count=metric.success_count,
        failure_count=metric.failure_count,
        input_tokens=metric.input_tokens,
        output_tokens=metric.output_tokens,
        cached_tokens=metric.cached_tokens,
        total_tokens=metric.total_tokens,
        cost_usd=metric.cost_usd,
        avg_latency_ms=metric.avg_latency_ms,
        cache_hit_count=metric.cache_hit_count,
        success_rate=metric.success_rate,
        cache_hit_rate=metric.cache_hit_rate,
    )


@router.get("/dashboard/summary", response_model=DashboardSummaryResponse)
async def dashboard_summary(
    team: CurrentTeam,
    reads: MgmtReads,
    days: int = Query(7, ge=1, le=90),
    usage_aggregation: UsageAggregation = Query(
        UsageAggregation.WORKSPACE,
        description=USAGE_AGGREGATION_QUERY_DESCRIPTION,
    ),
) -> DashboardSummaryResponse:
    end = datetime.now(UTC)
    start = end - timedelta(days=days)
    summary = await reads.aggregate_request_log_summary(
        team, start, end, usage_aggregation=usage_aggregation
    )
    total = summary["total"]
    success = summary["success"]
    show_cost = can_view_pricing_cost_fields(team)
    total_cost = summary["cost_usd"] if show_cost else Decimal("0")
    by_client = [
        DashboardClientTypeBreakdown(
            client_type=str(row["client_type"]),
            requests=int(row["requests"]),
            cost_usd=row["cost_usd"] if show_cost else Decimal("0"),
        )
        for row in summary.get("by_client_type", [])
    ]
    return DashboardSummaryResponse(
        total_requests=total,
        total_input_tokens=summary["input_tokens"],
        total_output_tokens=summary["output_tokens"],
        total_cost_usd=total_cost,
        success_count=success,
        failure_count=summary["failure"],
        avg_latency_ms=summary["avg_latency_ms"],
        success_rate=(success / total) if total else 0.0,
        by_client_type=by_client,
    )


@router.get("/dashboard/statistics", response_model=UsageStatisticsResponse)
async def dashboard_statistics(
    team: CurrentTeam,
    reads: MgmtReads,
    page: PageDep,
    days: int = Query(7, ge=1, le=365),
    usage_aggregation: UsageAggregation = Query(
        UsageAggregation.WORKSPACE,
        description=USAGE_AGGREGATION_QUERY_DESCRIPTION,
    ),
    group_by: UsageStatisticsGroupBy = Query(UsageStatisticsGroupBy.CREDENTIAL),
    credential_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    team_id: uuid.UUID | None = None,
    model: str | None = Query(default=None, min_length=1, max_length=200),
    provider: str | None = Query(default=None, min_length=1, max_length=50),
    capability: str | None = Query(default=None, min_length=1, max_length=40),
    status_filter: str | None = Query(default=None, alias="status", min_length=1, max_length=40),
    vkey_id: uuid.UUID | None = None,
) -> UsageStatisticsResponse:
    end = datetime.now(UTC)
    start = end - timedelta(days=days)
    summary, group_total = await reads.aggregate_usage_statistics(
        team,
        start,
        end,
        usage_aggregation=usage_aggregation,
        group_by=group_by,
        filters=UsageStatisticsFilters(
            credential_id=credential_id,
            user_id=user_id,
            team_id=team_id,
            model=model.strip() if model else None,
            provider=provider.strip() if provider else None,
            capability=capability.strip() if capability else None,
            status=status_filter.strip() if status_filter else None,
            vkey_id=vkey_id,
        ),
        page=page.page,
        page_size=page.page_size,
    )
    show_cost = can_view_pricing_cost_fields(team)
    return build_usage_statistics_response(
        items=[
            _usage_statistics_item_response(item, show_cost=show_cost)
            for item in summary.items
        ],
        total=group_total,
        page=page.page,
        page_size=page.page_size,
        start=summary.start,
        end=summary.end,
        group_by=summary.group_by,
        totals=_usage_stats_metric_response(summary.totals, show_cost=show_cost),
    )


def _breakdown_response(
    summary: UsageStatisticsBreakdownSummary,
) -> UsageStatisticsBreakdownResponse:
    return UsageStatisticsBreakdownResponse(
        parent_group_by=summary.parent_group_by,
        parent_group_key=summary.parent_group_key,
        breakdown_by=summary.breakdown_by,
        parent_requests=summary.parent_requests,
        items=[
            UsageStatisticsBreakdownSliceResponse(
                group_key=item.group_key,
                label=item.label,
                requests=item.requests,
                share=item.share,
            )
            for item in summary.items
        ],
    )


@router.get(
    "/dashboard/statistics/breakdown",
    response_model=UsageStatisticsBreakdownResponse,
)
async def dashboard_statistics_breakdown(
    team: CurrentTeam,
    reads: MgmtReads,
    days: int = Query(7, ge=1, le=365),
    usage_aggregation: UsageAggregation = Query(
        UsageAggregation.WORKSPACE,
        description=USAGE_AGGREGATION_QUERY_DESCRIPTION,
    ),
    parent_group_by: UsageStatisticsGroupBy = Query(...),
    parent_group_key: str = Query(..., min_length=0, max_length=200),
    breakdown_by: UsageStatisticsBreakdownBy = Query(...),
    top_n: int = Query(3, ge=1, le=32),
    credential_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    team_id: uuid.UUID | None = None,
    model: str | None = Query(default=None, min_length=1, max_length=200),
    provider: str | None = Query(default=None, min_length=1, max_length=50),
    capability: str | None = Query(default=None, min_length=1, max_length=40),
    status_filter: str | None = Query(default=None, alias="status", min_length=1, max_length=40),
    vkey_id: uuid.UUID | None = None,
) -> UsageStatisticsBreakdownResponse:
    end = datetime.now(UTC)
    start = end - timedelta(days=days)
    summary = await reads.aggregate_usage_statistics_breakdown(
        team,
        start,
        end,
        usage_aggregation=usage_aggregation,
        filters=UsageStatisticsFilters(
            credential_id=credential_id,
            user_id=user_id,
            team_id=team_id,
            model=model.strip() if model else None,
            provider=provider.strip() if provider else None,
            capability=capability.strip() if capability else None,
            status=status_filter.strip() if status_filter else None,
            vkey_id=vkey_id,
        ),
        parent_group_by=parent_group_by,
        parent_group_key=parent_group_key,
        breakdown_by=breakdown_by,
        top_n=top_n,
    )
    return _breakdown_response(summary)


@router.get(
    "/dashboard/margin",
    response_model=MarginSummaryResponse,
)
async def dashboard_margin(
    team: CurrentTeam,
    reads: MgmtReads,
    days: int = Query(30, ge=1, le=365),
    group_by: MarginGroupBy = Query("credential"),
) -> MarginSummaryResponse:
    if not can_view_margin_dashboard(team):
        raise PermissionDeniedError(
            message="margin dashboard requires platform admin",
            resource="margin dashboard",
        )
    end = datetime.now(UTC)
    start = end - timedelta(days=days)
    summary = await reads.get_team_margin_summary(
        team.team_id, since=start, until=end, group_by=group_by
    )
    return MarginSummaryResponse(
        period_start=summary.period_start,
        period_end=summary.period_end,
        total_revenue_usd=summary.total_revenue_usd,
        total_cost_usd=summary.total_cost_usd,
        total_margin_usd=summary.total_margin_usd,
        group_by=summary.group_by,
        group_column_label=summary.group_column_label,
        items=[
            MarginGroupItemResponse(
                group_key=i.group_key,
                label=i.label,
                revenue_usd=i.revenue_usd,
                cost_usd=i.cost_usd,
                margin_usd=i.margin_usd,
                margin_ratio=i.margin_ratio,
            )
            for i in summary.items
        ],
    )


__all__ = ["router"]
