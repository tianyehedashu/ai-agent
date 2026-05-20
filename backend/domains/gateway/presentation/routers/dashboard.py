"""Dashboard 子 router (含 /dashboard/summary 与 /dashboard/margin)。

Stage 2 起：``aggregate_request_log_summary`` 经 ``UsageAxis`` 统一访问仓储。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Query

from domains.gateway.domain.margin_read_model import MarginGroupBy
from domains.gateway.domain.usage_read_model import (
    USAGE_AGGREGATION_QUERY_DESCRIPTION,
    UsageAggregation,
)
from domains.gateway.presentation.deps import CurrentTeam
from domains.gateway.presentation.schemas.common import (
    DashboardClientTypeBreakdown,
    DashboardSummaryResponse,
    MarginGroupItemResponse,
    MarginSummaryResponse,
)

from ._common import MgmtReads

router = APIRouter()


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
    by_client = [
        DashboardClientTypeBreakdown(
            client_type=str(row["client_type"]),
            requests=int(row["requests"]),
            cost_usd=row["cost_usd"],
        )
        for row in summary.get("by_client_type", [])
    ]
    return DashboardSummaryResponse(
        total_requests=total,
        total_input_tokens=summary["input_tokens"],
        total_output_tokens=summary["output_tokens"],
        total_cost_usd=summary["cost_usd"],
        success_count=success,
        failure_count=summary["failure"],
        avg_latency_ms=summary["avg_latency_ms"],
        success_rate=(success / total) if total else 0.0,
        by_client_type=by_client,
    )


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
