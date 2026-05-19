"""团队月度对账聚合（cost / revenue / 毛利）。"""

from __future__ import annotations

from calendar import monthrange
from datetime import UTC, datetime
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from domains.gateway.domain.usage_axis import UsageAxis
from domains.gateway.infrastructure.repositories.request_log_repository import (
    RequestLogRepository,
)


async def team_month_reconciliation(
    session: AsyncSession,
    *,
    team_id: uuid.UUID,
    year: int,
    month: int,
) -> dict[str, object]:
    last_day = monthrange(year, month)[1]
    start = datetime(year, month, 1, tzinfo=UTC)
    end = datetime(year, month, last_day, 23, 59, 59, tzinfo=UTC)
    axis = UsageAxis.workspace(team_id)
    repo = RequestLogRepository(session)
    summary = await repo.aggregate_billing_summary_by_axis(axis, start, end)
    top = await repo.aggregate_top_routes_billing_by_axis(axis, start, end, limit=50)
    return {
        "team_id": str(team_id),
        "period": f"{year:04d}-{month:02d}",
        "requests": summary["requests"],
        "cost_usd": str(summary["cost_usd"]),
        "revenue_usd": str(summary["revenue_usd"]),
        "margin_usd": str(summary["margin_usd"]),
        "top_models": [
            {
                "route_name": row["route_name"],
                "requests": row["requests"],
                "cost_usd": str(row["cost_usd"]),
                "revenue_usd": str(row["revenue_usd"]),
                "margin_usd": str(row["margin_usd"]),
            }
            for row in top
        ],
    }


__all__ = ["team_month_reconciliation"]
