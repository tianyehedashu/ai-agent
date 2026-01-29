"""
Usage Router - 配额与用量 API

提供用户配额状态与用量日志查询。
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from domains.identity.infrastructure.repositories.user_quota_repository import UserQuotaRepository
from domains.identity.presentation.deps import RequiredAuthUser, get_user_uuid
from libs.api.deps import DbSession

router = APIRouter()


# =============================================================================
# Schemas
# =============================================================================


class QuotaStatusResponse(BaseModel):
    """配额状态响应"""

    user_id: UUID
    daily_text_requests: int | None
    daily_image_requests: int | None
    daily_embedding_requests: int | None
    monthly_token_limit: int | None
    current_daily_text: int = 0
    current_daily_image: int = 0
    current_daily_embedding: int = 0
    current_monthly_tokens: int = 0
    daily_reset_at: datetime | None = None
    monthly_reset_at: datetime | None = None


class UsageLogResponse(BaseModel):
    """用量日志响应"""

    id: UUID
    capability: str
    provider: str
    model: str | None
    key_source: str
    input_tokens: int | None
    output_tokens: int | None
    image_count: int | None
    cost_estimate: Decimal | None
    created_at: datetime

    model_config = {"from_attributes": True}


# =============================================================================
# Dependencies
# =============================================================================


def get_quota_repo(db: DbSession) -> UserQuotaRepository:
    """获取用户配额仓储"""
    return UserQuotaRepository(db)


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
    repo: UserQuotaRepository = Depends(get_quota_repo),
) -> QuotaStatusResponse | None:
    """获取当前用户的配额状态"""
    user_id = get_user_uuid(current_user)
    quota = await repo.get_by_user(user_id)
    if not quota:
        return None
    return QuotaStatusResponse(
        user_id=quota.user_id,
        daily_text_requests=quota.daily_text_requests,
        daily_image_requests=quota.daily_image_requests,
        daily_embedding_requests=quota.daily_embedding_requests,
        monthly_token_limit=quota.monthly_token_limit,
        current_daily_text=quota.current_daily_text,
        current_daily_image=quota.current_daily_image,
        current_daily_embedding=quota.current_daily_embedding,
        current_monthly_tokens=quota.current_monthly_tokens,
        daily_reset_at=quota.daily_reset_at,
        monthly_reset_at=quota.monthly_reset_at,
    )


@router.get(
    "/logs",
    response_model=list[UsageLogResponse],
    tags=["Usage"],
)
async def get_usage_logs(
    current_user: RequiredAuthUser,
    repo: UserQuotaRepository = Depends(get_quota_repo),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[UsageLogResponse]:
    """获取当前用户的用量日志"""
    user_id = get_user_uuid(current_user)
    logs = await repo.get_usage_logs(user_id, limit=limit, offset=offset)
    return [UsageLogResponse.model_validate(log) for log in logs]
