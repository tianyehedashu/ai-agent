"""
System API - 系统接口
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from bootstrap.config import settings
from domains.agent.application.stats_service import StatsService
from domains.agent.infrastructure.llm import get_all_models
from domains.identity.presentation.deps import OptionalUser
from libs.api.deps import get_stats_service

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


class SimpleModelInfo(BaseModel):
    """简单模型信息（用于下拉选择）"""

    value: str
    label: str
    provider: str


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """健康检查"""
    return HealthResponse(
        status="healthy",
        service=settings.app_name,
        version=__import__("bootstrap").__version__,
        environment=settings.app_env,
        timestamp=datetime.now(UTC),
    )


@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    current_user: OptionalUser,
    stats_service: StatsService = Depends(get_stats_service),
) -> StatsResponse:
    """获取系统统计信息"""
    stats = await stats_service.get_system_stats()
    return StatsResponse(**stats)


@router.get("/models", response_model=list[ModelInfo])
async def list_available_models(
    current_user: OptionalUser,
) -> list[ModelInfo]:
    """
    获取可用模型列表

    根据配置API Key返回可用的模型列表。支持: Anthropic, OpenAI, 阿里云通义千问, DeepSeek, 火山引擎豆包
    """
    # 定义所有支持的模型
    all_models = [
        # Anthropic (Claude)
        ModelInfo(
            name="claude-3-5-sonnet-20241022",
            provider="anthropic",
            context_window=200000,
            supports_tools=True,
            supports_vision=True,
        ),
        ModelInfo(
            name="claude-3-5-haiku-20241022",
            provider="anthropic",
            context_window=200000,
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
        # OpenAI (GPT)
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
            name="o1-preview",
            provider="openai",
            context_window=128000,
            supports_tools=False,
            supports_vision=True,
        ),
        ModelInfo(
            name="o1-mini",
            provider="openai",
            context_window=128000,
            supports_tools=False,
            supports_vision=True,
        ),
        # 阿里DashScope (通义千问 Qwen)
        ModelInfo(
            name="qwen-max",
            provider="dashscope",
            context_window=32000,
            supports_tools=True,
            supports_vision=False,
        ),
        ModelInfo(
            name="qwen-max-longcontext",
            provider="dashscope",
            context_window=1000000,
            supports_tools=True,
            supports_vision=False,
        ),
        ModelInfo(
            name="qwen-plus",
            provider="dashscope",
            context_window=131072,
            supports_tools=True,
            supports_vision=False,
        ),
        ModelInfo(
            name="qwen-turbo",
            provider="dashscope",
            context_window=131072,
            supports_tools=True,
            supports_vision=False,
        ),
        ModelInfo(
            name="qwen-vl-max",
            provider="dashscope",
            context_window=32000,
            supports_tools=True,
            supports_vision=True,
        ),
        ModelInfo(
            name="qwen2.5-coder-32b-instruct",
            provider="dashscope",
            context_window=131072,
            supports_tools=True,
            supports_vision=False,
        ),
        # DeepSeek
        ModelInfo(
            name="deepseek-chat",
            provider="deepseek",
            context_window=64000,
            supports_tools=True,
            supports_vision=False,
        ),
        ModelInfo(
            name="deepseek-coder",
            provider="deepseek",
            context_window=64000,
            supports_tools=True,
            supports_vision=False,
        ),
        ModelInfo(
            name="deepseek-reasoner",
            provider="deepseek",
            context_window=64000,
            supports_tools=True,
            supports_vision=False,
        ),
        # 火山引擎 (豆包)
        ModelInfo(
            name="doubao-pro-128k",
            provider="volcengine",
            context_window=128000,
            supports_tools=True,
            supports_vision=False,
        ),
        ModelInfo(
            name="doubao-pro-32k",
            provider="volcengine",
            context_window=32000,
            supports_tools=True,
            supports_vision=False,
        ),
        ModelInfo(
            name="doubao-lite-128k",
            provider="volcengine",
            context_window=128000,
            supports_tools=True,
            supports_vision=False,
        ),
        ModelInfo(
            name="doubao-lite-32k",
            provider="volcengine",
            context_window=32000,
            supports_tools=True,
            supports_vision=False,
        ),
    ]

    # 检查API Key是否配置，只返回可用的模型
    available_models = []

    if settings.anthropic_api_key:
        available_models.extend([m for m in all_models if m.provider == "anthropic"])

    if settings.openai_api_key:
        available_models.extend([m for m in all_models if m.provider == "openai"])

    if settings.dashscope_api_key:
        available_models.extend([m for m in all_models if m.provider == "dashscope"])

    if settings.deepseek_api_key:
        available_models.extend([m for m in all_models if m.provider == "deepseek"])

    if settings.volcengine_api_key:
        available_models.extend([m for m in all_models if m.provider == "volcengine"])

    if settings.zhipuai_api_key:
        available_models.extend([m for m in all_models if m.provider == "zhipuai"])

    return available_models


@router.get("/models/simple", response_model=list[SimpleModelInfo])
async def list_available_models_simple(
    current_user: OptionalUser,
) -> list[SimpleModelInfo]:
    """
    获取可用模型列表（简单格式）

    返回格式化的模型列表，用于前端下拉选择。根据配置API Key返回可用的模型列表。
    """
    # 获取所有支持的模型（按提供商分组）
    all_models_by_provider = get_all_models()

    # 模型显示名称映射
    model_labels: dict[str, str] = {
        # Anthropic (Claude)
        "claude-3-5-sonnet-20241022": "Claude 3.5 Sonnet",
        "claude-3-5-haiku-20241022": "Claude 3.5 Haiku",
        "claude-3-opus-20240229": "Claude 3 Opus",
        "claude-3-sonnet-20240229": "Claude 3 Sonnet",
        "claude-3-haiku-20240307": "Claude 3 Haiku",
        # OpenAI (GPT)
        "gpt-4": "GPT-4",
        "gpt-4-turbo": "GPT-4 Turbo",
        "gpt-4o": "GPT-4o",
        "gpt-4o-mini": "GPT-4o Mini",
        "gpt-3.5-turbo": "GPT-3.5 Turbo",
        "o1-preview": "O1 Preview",
        "o1-mini": "O1 Mini",
        # 阿里DashScope (通义千问 Qwen)
        "qwen-turbo": "通义千问 Turbo",
        "qwen-turbo-latest": "通义千问 Turbo (最新)",
        "qwen-plus": "通义千问 Plus",
        "qwen-plus-latest": "通义千问 Plus (最新)",
        "qwen-max": "通义千问 Max",
        "qwen-max-latest": "通义千问 Max (最新)",
        "qwen-max-longcontext": "通义千问 Max (长上下文)",
        "qwen-vl-plus": "通义千问 VL Plus",
        "qwen-vl-max": "通义千问 VL Max",
        "qwen2.5-72b-instruct": "通义千问 2.5 72B",
        "qwen2.5-32b-instruct": "通义千问 2.5 32B",
        "qwen2.5-14b-instruct": "通义千问 2.5 14B",
        "qwen2.5-7b-instruct": "通义千问 2.5 7B",
        "qwen2.5-coder-32b-instruct": "通义千问 2.5 Coder 32B",
        # DeepSeek
        "deepseek-chat": "DeepSeek Chat",
        "deepseek-coder": "DeepSeek Coder",
        "deepseek-reasoner": "DeepSeek Reasoner",
        # 火山引擎 (豆包)
        "doubao-pro-32k": "豆包 Pro (32K)",
        "doubao-pro-128k": "豆包 Pro (128K)",
        "doubao-pro-256k": "豆包 Pro (256K)",
        "doubao-lite-32k": "豆包 Lite (32K)",
        "doubao-lite-128k": "豆包 Lite (128K)",
        "doubao-character-pro-32k": "豆包 Character Pro (32K)",
        # 智谱AI (GLM)
        "glm-4.7": "GLM-4.7",
        "glm-4": "GLM-4",
        "glm-4-plus": "GLM-4 Plus",
        "glm-4-air": "GLM-4 Air",
        "glm-4-flash": "GLM-4 Flash",
    }

    # 检查API Key是否配置，只返回可用的模型
    available_models: list[SimpleModelInfo] = []

    # Anthropic
    if settings.anthropic_api_key and "anthropic" in all_models_by_provider:
        for model in all_models_by_provider["anthropic"]:
            available_models.append(
                SimpleModelInfo(
                    value=model,
                    label=model_labels.get(model, model),
                    provider="anthropic",
                )
            )

    # OpenAI
    if settings.openai_api_key and "openai" in all_models_by_provider:
        for model in all_models_by_provider["openai"]:
            available_models.append(
                SimpleModelInfo(
                    value=model,
                    label=model_labels.get(model, model),
                    provider="openai",
                )
            )

    # 阿里DashScope
    if settings.dashscope_api_key and "dashscope" in all_models_by_provider:
        for model in all_models_by_provider["dashscope"]:
            available_models.append(
                SimpleModelInfo(
                    value=model,
                    label=model_labels.get(model, model),
                    provider="dashscope",
                )
            )

    # DeepSeek
    if settings.deepseek_api_key and "deepseek" in all_models_by_provider:
        for model in all_models_by_provider["deepseek"]:
            available_models.append(
                SimpleModelInfo(
                    value=model,
                    label=model_labels.get(model, model),
                    provider="deepseek",
                )
            )

    # 火山引擎
    if settings.volcengine_api_key and "volcengine" in all_models_by_provider:
        for model in all_models_by_provider["volcengine"]:
            available_models.append(
                SimpleModelInfo(
                    value=model,
                    label=model_labels.get(model, model),
                    provider="volcengine",
                )
            )

    # 智谱AI
    if settings.zhipuai_api_key and "zhipuai" in all_models_by_provider:
        for model in all_models_by_provider["zhipuai"]:
            available_models.append(
                SimpleModelInfo(
                    value=model,
                    label=model_labels.get(model, model),
                    provider="zhipuai",
                )
            )

    # 按提供商和模型名称排序
    available_models.sort(key=lambda x: (x.provider, x.value))

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
