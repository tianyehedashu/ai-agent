"""Gateway 运行时能力开关（与部署 env 对齐，供控制台读取）。"""

from __future__ import annotations

from fastapi import APIRouter

from bootstrap.config import settings
from domains.gateway.presentation.deps import CurrentTeam
from domains.gateway.presentation.schemas.common import GatewayFeaturesResponse

router = APIRouter()


@router.get("/features", response_model=GatewayFeaturesResponse)
async def get_gateway_features(_team: CurrentTeam) -> GatewayFeaturesResponse:
    """返回全局 Gateway 能力开关（如 PII 守卫是否已在 LiteLLM 注册）。"""
    return GatewayFeaturesResponse(
        pii_guardrail_globally_enabled=settings.gateway_default_guardrail_enabled,
    )
