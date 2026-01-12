"""
System API - 系统接口
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from api.deps import get_current_user_optional, get_stats_service
from app.config import settings
from models.user import User
from services.stats import StatsService

router = APIRouter()


class HealthResponse(BaseModel):
    """健康检查响应"""

    status: str
    service: str
    version: str
    environment: str
    timestamp: datetime


class StatsResponse(BaseModel):
    """统计信息响应"""

    total_users: int
    total_agents: int
    total_sessions: int
    total_messages: int
    active_sessions_today: int


class ModelInfo(BaseModel):
    """模型信息"""

    name: str
    provider: str
    context_window: int
    supports_tools: bool
    supports_vision: bool


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """健康检查"""
    return HealthResponse(
        status="healthy",
        service=settings.app_name,
        version=__import__("app").__version__,
        environment=settings.app_env,
        timestamp=datetime.now(timezone.utc),
    )


@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    current_user: User | None = Depends(get_current_user_optional),
    stats_service: StatsService = Depends(get_stats_service),
) -> StatsResponse:
    """获取系统统计信息"""
    stats = await stats_service.get_system_stats()
    return StatsResponse(**stats)


@router.get("/models", response_model=list[ModelInfo])
async def list_available_models(
    current_user: User | None = Depends(get_current_user_optional),
) -> list[ModelInfo]:
    """获取可用模型列表"""
    # 定义可用模型
    models = [
        ModelInfo(
            name="claude-3-5-sonnet-20241022",
            provider="anthropic",
            context_window=200000,
            supports_tools=True,
            supports_vision=True,
        ),
        ModelInfo(
            name="gpt-4o",
            provider="openai",
            context_window=128000,
            supports_tools=True,
            supports_vision=True,
        ),
        ModelInfo(
            name="gpt-4o-mini",
            provider="openai",
            context_window=128000,
            supports_tools=True,
            supports_vision=True,
        ),
        ModelInfo(
            name="gpt-4-turbo",
            provider="openai",
            context_window=128000,
            supports_tools=True,
            supports_vision=True,
        ),
        ModelInfo(
            name="claude-3-opus-20240229",
            provider="anthropic",
            context_window=200000,
            supports_tools=True,
            supports_vision=True,
        ),
        ModelInfo(
            name="claude-3-haiku-20240307",
            provider="anthropic",
            context_window=200000,
            supports_tools=True,
            supports_vision=True,
        ),
    ]

    # 检查 API Key 是否配置，只返回可用的模型
    available_models = []
    if settings.anthropic_api_key:
        available_models.extend([m for m in models if m.provider == "anthropic"])
    if settings.openai_api_key:
        available_models.extend([m for m in models if m.provider == "openai"])

    return available_models


@router.get("/config")
async def get_public_config() -> dict:
    """获取公开配置"""
    return {
        "app_name": settings.app_name,
        "environment": settings.app_env,
        "features": {
            "sandbox_enabled": settings.sandbox_enabled,
            "hitl_enabled": settings.hitl_enabled,
            "checkpoint_enabled": settings.checkpoint_enabled,
            "metrics_enabled": settings.metrics_enabled,
        },
        "limits": {
            "max_iterations": settings.agent_max_iterations,
            "max_tokens": settings.agent_max_tokens,
            "timeout_seconds": settings.agent_timeout_seconds,
        },
    }
