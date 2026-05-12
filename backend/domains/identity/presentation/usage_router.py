"""
Usage Router - 配额与用量 API（兼容层）

历史接口 /api/v1/usage/quota 与 /api/v1/usage/logs 保留以避免破坏前端。
内部已切换为读取新的 GatewayBudget 与 GatewayRequestLog 表。

新代码请直接使用 /api/v1/gateway/budgets 与 /api/v1/gateway/logs。
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import select

from domains.gateway.infrastructure.models.budget import GatewayBudget
from domains.gateway.infrastructure.models.request_log import GatewayRequestLog
from domains.gateway.infrastructure.models.team import Team
from domains.identity.presentation.deps import RequiredAuthUser, get_user_uuid
from libs.api.deps import DbSession

router = APIRouter()


# =============================================================================
# Schemas（保持向后兼容）
# =============================================================================


class QuotaStatusResponse(BaseModel):
    """配额状态响应（兼容旧字段名）"""

    user_id: UUID
    daily_text_requests: int | None = None
    daily_image_requests: int | None = None
    daily_embedding_requests: int | None = None
    monthly_token_limit: int | None = None
    current_daily_text: int = 0
    current_daily_image: int = 0
    current_daily_embedding: int = 0
    current_monthly_tokens: int = 0
    daily_reset_at: datetime | None = None
    monthly_reset_at: datetime | None = None


class UsageLogResponse(BaseModel):
    """用量日志响应（兼容旧字段名）"""

    id: UUID
    capability: str
    provider: str
    model: str | None
    key_source: str
    input_tokens: int | None
    output_tokens: int | None
    image_count: int | None = None
    cost_estimate: Decimal | None
    created_at: datetime


# =============================================================================
# Routes
# =============================================================================


@router.get(
    "/quota",
    response_model=QuotaStatusResponse | None,
    tags=["Usage"],
)
async def get_quota_status(
    current_user: RequiredAuthUser,
    db: DbSession,
) -> QuotaStatusResponse | None:
    """获取当前用户的配额状态（聚合 daily/monthly Budget）"""
    user_id = get_user_uuid(current_user)

    # 取 user 维度的 daily / monthly budget
    daily = (
        await db.execute(
            select(GatewayBudget).where(
                GatewayBudget.scope == "user",
                GatewayBudget.scope_id == user_id,
                GatewayBudget.period == "daily",
            )
        )
    ).scalar_one_or_none()
    monthly = (
        await db.execute(
            select(GatewayBudget).where(
                GatewayBudget.scope == "user",
                GatewayBudget.scope_id == user_id,
                GatewayBudget.period == "monthly",
            )
        )
    ).scalar_one_or_none()

    if daily is None and monthly is None:
        return None

    return QuotaStatusResponse(
        user_id=user_id,
        daily_text_requests=daily.limit_requests if daily else None,
        monthly_token_limit=monthly.limit_tokens if monthly else None,
        current_daily_text=daily.current_requests if daily else 0,
        current_monthly_tokens=monthly.current_tokens if monthly else 0,
        daily_reset_at=daily.reset_at if daily else None,
        monthly_reset_at=monthly.reset_at if monthly else None,
    )


@router.get(
    "/logs",
    response_model=list[UsageLogResponse],
    tags=["Usage"],
)
async def get_usage_logs(
    current_user: RequiredAuthUser,
    db: DbSession,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[UsageLogResponse]:
    """获取当前用户的用量日志（从 GatewayRequestLog 读）"""
    user_id = get_user_uuid(current_user)
    # 取该用户名下任一团队的日志（personal 团队优先）
    team_ids_subq = select(Team.id).where(Team.owner_user_id == user_id)
    stmt = (
        select(GatewayRequestLog)
        .where(
            (GatewayRequestLog.user_id == user_id)
            | (GatewayRequestLog.team_id.in_(team_ids_subq))
        )
        .where(GatewayRequestLog.created_at >= datetime.now(UTC) - timedelta(days=90))
        .order_by(GatewayRequestLog.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    logs = list(result.scalars().all())
    return [
        UsageLogResponse(
            id=log.id,
            capability=log.capability,
            provider=log.provider or "unknown",
            model=log.real_model,
            key_source="vkey" if log.vkey_id else "system",
            input_tokens=log.input_tokens,
            output_tokens=log.output_tokens,
            image_count=None,
            cost_estimate=log.cost_usd,
            created_at=log.created_at,
        )
        for log in logs
    ]
