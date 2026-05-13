"""
Usage Router - 配额与用量 API（兼容层）

历史接口 /api/v1/usage/quota 与 /api/v1/usage/logs 保留以避免破坏前端。
只读数据经 GatewayUsageReadService，不直连 gateway ORM。

新代码请直接使用 /api/v1/gateway/budgets 与 /api/v1/gateway/logs。
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel

from domains.gateway.application.management import GatewayUsageReadService
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
    svc = GatewayUsageReadService(db)
    snap = await svc.get_user_quota_snapshot(user_id)
    if snap is None:
        return None

    return QuotaStatusResponse(
        user_id=snap.user_id,
        daily_text_requests=snap.daily_text_requests,
        monthly_token_limit=snap.monthly_token_limit,
        current_daily_text=snap.current_daily_text,
        current_monthly_tokens=snap.current_monthly_tokens,
        daily_reset_at=snap.daily_reset_at,
        monthly_reset_at=snap.monthly_reset_at,
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
    svc = GatewayUsageReadService(db)
    rows = await svc.list_recent_usage_logs_for_user(
        user_id,
        limit=limit,
        offset=offset,
    )
    return [
        UsageLogResponse(
            id=r.id,
            capability=r.capability,
            provider=r.provider,
            model=r.model,
            key_source=r.key_source,
            input_tokens=r.input_tokens,
            output_tokens=r.output_tokens,
            image_count=r.image_count,
            cost_estimate=r.cost_estimate,
            created_at=r.created_at,
        )
        for r in rows
    ]
