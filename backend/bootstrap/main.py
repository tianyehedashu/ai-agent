"""
AI Agent Backend - Main Application

FastAPI 应用入口点
"""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
import inspect
import sys
import traceback
from typing import Any
import warnings

# Windows 需要使用 SelectorEventLoop（psycopg 异步要求）
# 必须在导入可能依赖事件循环的模块之前设置
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# pylint: disable=wrong-import-position
# 这些导入必须在事件循环设置之后，以确保 Windows 平台上的异步操作正常工作
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from bootstrap.config import settings
from domains.agent.application.startup import (
    agent_streamable_http_lifespan,
    run_agent_shutdown,
    run_agent_startup,
)

# 从各领域的 presentation 层导入路由
from domains.agent.presentation.agent_router import router as agent_router
from domains.agent.presentation.chat_router import router as chat_router
from domains.agent.presentation.execution_router import router as execution_router
from domains.agent.presentation.mcp_router import router as mcp_router
from domains.agent.presentation.mcp_server_router import router as mcp_server_router
from domains.agent.presentation.memory_router import router as memory_router
from domains.agent.presentation.listing_studio_router import router as listing_studio_router
from domains.agent.presentation.admin_storage_router import router as admin_storage_router
from domains.agent.presentation.product_info_router import router as product_info_router
from domains.agent.presentation.system_router import router as system_router
from domains.agent.presentation.tools_router import router as tools_router
from domains.agent.presentation.video_task_router import router as video_task_router
from domains.evaluation.presentation.router import router as evaluation_router
from domains.gateway.application.startup import run_gateway_shutdown, run_gateway_startup
from domains.gateway.presentation.anthropic_compat_router import router as anthropic_compat_router
from domains.gateway.presentation.management_router import router as gateway_mgmt_router
from domains.gateway.presentation.openai_compat_router import router as openai_compat_router
from domains.identity.infrastructure.auth.jwt import init_jwt_manager
from domains.identity.presentation.api_key_router import router as api_key_router
from domains.identity.presentation.router import router as identity_router
from domains.identity.presentation.usage_router import router as usage_router
from domains.session.presentation import session_router
from domains.tenancy.presentation.teams_router import router as tenancy_teams_router
from libs.background_tasks import init_background_tasks, shutdown_app_background_tasks
from libs.db.database import init_db
from libs.db.redis import close_redis, init_redis
from libs.exceptions import (
    AIAgentError,
    AuthenticationError,
    CheckpointError,
    ConflictError,
    ExternalServiceError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    TokenError,
    ToolExecutionError,
    ValidationError,
)
from libs.middleware.anonymous_cookie_asgi import AnonymousCookieASGIMiddleware
from libs.middleware.permission import PermissionContextASGIMiddleware
from utils.logging import get_logger, setup_logging

# pylint: enable=wrong-import-position

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_fastapi_app: FastAPI) -> AsyncGenerator[None, None]:  # pylint: disable=too-many-statements
    """应用生命周期管理"""
    # 启动时 - 输出环境配置以便调试
    logger.info("=" * 60)
    logger.info("启动 AI Agent Backend")
    logger.info("  APP_ENV: %s (is_development=%s)", settings.app_env, settings.is_development)
    logger.info("  DEBUG: %s", settings.debug)
    logger.info("=" * 60)

    setup_logging(
        log_level=settings.log_level,
        log_format=settings.log_format,
        is_development=settings.is_development,
    )

    # 抑制 LiteLLM 内部的 Pydantic 序列化警告（这是 LiteLLM 内部问题，不影响功能）
    warnings.filterwarnings(
        "ignore",
        message=".*PydanticSerializationUnexpectedValue.*",
        category=UserWarning,
        module="pydantic",
    )
    warnings.filterwarnings(
        "ignore",
        category=RuntimeWarning,
        module="litellm",
    )

    # 初始化 JWT Manager
    init_jwt_manager(settings)

    # 设置 LiteLLM 环境变量

    # 初始化数据库
    await init_db()

    await run_gateway_startup(_fastapi_app)

    # 初始化 Redis（开发机未起 redis 时仅告警，不阻断启动）
    try:
        await init_redis()
    except Exception as e:  # noqa: BLE001 — redis/asyncio 可能抛多种连接异常
        logger.warning("Redis not available: %s", e)

    await run_agent_startup(_fastapi_app)

    init_background_tasks(_fastapi_app)

    async with agent_streamable_http_lifespan():
        yield

    # 关闭时
    await shutdown_app_background_tasks(_fastapi_app)
    await run_gateway_shutdown(_fastapi_app)
    await run_agent_shutdown(_fastapi_app)

    # 清理 LiteLLM 异步客户端
    try:
        import litellm  # pylint: disable=import-outside-toplevel

        _close = getattr(litellm, "close_litellm_async_clients", None)
        if callable(_close):
            _maybe = _close()
            if inspect.isawaitable(_maybe):
                await _maybe
            logger.info("LiteLLM async clients closed successfully")
    except Exception as e:
        logger.warning("Error closing LiteLLM async clients: %s", e)

    await close_redis()


# 创建 FastAPI 应用
app = FastAPI(
    title=settings.app_name,
    description="AI Agent 系统后端 API",
    version="0.1.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan,
)

# CORS 中间件
# 注意：allow_credentials=True 时不能使用 allow_origins=["*"]
# 必须明确指定允许的源
cors_origins = (
    ["http://localhost:3000", "http://localhost:8000", "http://127.0.0.1:3000"]
    if settings.debug
    else settings.cors_origins
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,  # 允许携带 Cookie
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[
        "X-Anonymous-User-Id",
        "Retry-After",
        "x-ratelimit-limit-requests",
        "x-ratelimit-remaining-requests",
        "x-ratelimit-reset-requests",
        "x-ratelimit-limit-tokens",
        "x-ratelimit-remaining-tokens",
        "x-ratelimit-reset-tokens",
        "anthropic-ratelimit-requests-limit",
        "anthropic-ratelimit-requests-remaining",
        "anthropic-ratelimit-requests-reset",
        "anthropic-ratelimit-tokens-limit",
        "anthropic-ratelimit-tokens-remaining",
        "anthropic-ratelimit-tokens-reset",
    ],
)

# 纯 ASGI 中间件（与 SSE/StreamingResponse 兼容；勿改用 @app.middleware + BaseHTTPMiddleware）
app.add_middleware(PermissionContextASGIMiddleware)
app.add_middleware(AnonymousCookieASGIMiddleware)


# =============================================================================
# 全局异常处理器
# =============================================================================


def _error_response(
    status_code: int,
    message: str,
    code: str | None = None,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    """构建错误响应"""
    content: dict[str, Any] = {"detail": message}
    if code:
        content["code"] = code
    if details:
        content["details"] = details
    return JSONResponse(status_code=status_code, content=content)


@app.exception_handler(ValidationError)
async def validation_error_handler(
    _request: Request,
    exc: ValidationError,
) -> JSONResponse:
    """处理验证错误"""
    logger.warning("Validation error: %s", exc.message)
    return _error_response(
        status_code=status.HTTP_400_BAD_REQUEST,
        message=exc.message,
        code=exc.code,
        details=exc.details,
    )


@app.exception_handler(NotFoundError)
async def not_found_error_handler(
    _request: Request,
    exc: NotFoundError,
) -> JSONResponse:
    """处理资源不存在错误"""
    logger.warning("Resource not found: %s", exc.message)
    return _error_response(
        status_code=status.HTTP_404_NOT_FOUND,
        message=exc.message,
        code=exc.code,
        details=exc.details,
    )


@app.exception_handler(PermissionDeniedError)
async def permission_denied_error_handler(
    _request: Request,
    exc: PermissionDeniedError,
) -> JSONResponse:
    """处理权限不足错误"""
    logger.warning("Permission denied: %s", exc.message)
    return _error_response(
        status_code=status.HTTP_403_FORBIDDEN,
        message=exc.message,
        code=exc.code,
        details=exc.details,
    )


@app.exception_handler(AuthenticationError)
async def authentication_error_handler(
    _request: Request,
    exc: AuthenticationError,
) -> JSONResponse:
    """处理认证错误"""
    logger.warning("Authentication failed: %s", exc.message)
    return _error_response(
        status_code=status.HTTP_401_UNAUTHORIZED,
        message=exc.message,
        code=exc.code,
    )


@app.exception_handler(TokenError)
async def token_error_handler(
    _request: Request,
    exc: TokenError,
) -> JSONResponse:
    """处理 Token 错误"""
    logger.warning("Token error: %s", exc.message)
    return _error_response(
        status_code=status.HTTP_401_UNAUTHORIZED,
        message=exc.message,
        code=exc.code,
    )


@app.exception_handler(ConflictError)
async def conflict_error_handler(
    _request: Request,
    exc: ConflictError,
) -> JSONResponse:
    """处理资源冲突错误"""
    logger.warning("Resource conflict: %s", exc.message)
    return _error_response(
        status_code=status.HTTP_409_CONFLICT,
        message=exc.message,
        code=exc.code,
        details=exc.details,
    )


@app.exception_handler(RateLimitError)
async def rate_limit_error_handler(
    _request: Request,
    exc: RateLimitError,
) -> JSONResponse:
    """处理速率限制错误"""
    logger.warning("Rate limit exceeded: %s", exc.message)
    headers = {}
    if exc.retry_after:
        headers["Retry-After"] = str(exc.retry_after)
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"detail": exc.message, "code": exc.code},
        headers=headers,
    )


@app.exception_handler(ExternalServiceError)
async def external_service_error_handler(
    _request: Request,
    exc: ExternalServiceError,
) -> JSONResponse:
    """处理外部服务错误"""
    logger.error("External service error: %s - %s", exc.service, exc.message)
    return _error_response(
        status_code=status.HTTP_502_BAD_GATEWAY,
        message=exc.message,
        code=exc.code,
        details=exc.details,
    )


@app.exception_handler(ToolExecutionError)
async def tool_execution_error_handler(
    _request: Request,
    exc: ToolExecutionError,
) -> JSONResponse:
    """处理工具执行错误"""
    logger.error("Tool execution error: %s - %s", exc.tool_name, exc.message)
    return _error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        message=exc.message,
        code=exc.code,
        details=exc.details,
    )


@app.exception_handler(CheckpointError)
async def checkpoint_error_handler(
    _request: Request,
    exc: CheckpointError,
) -> JSONResponse:
    """处理检查点错误"""
    logger.error("Checkpoint error: %s", exc.message)
    return _error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        message=exc.message,
        code=exc.code,
        details=exc.details,
    )


@app.exception_handler(AIAgentError)
async def ai_agent_error_handler(
    _request: Request,
    exc: AIAgentError,
) -> JSONResponse:
    """处理通用 AI Agent 错误"""
    logger.error("AI Agent error: %s", exc.message)
    return _error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        message=exc.message,
        code=exc.code,
        details=exc.details,
    )


@app.exception_handler(Exception)
async def general_exception_handler(
    _request: Request,
    exc: Exception,
) -> JSONResponse:
    """处理未捕获的异常"""
    # 确保异常日志被输出（使用 exception 会自动包含堆栈）
    logger.exception("Unhandled exception: %s", exc)

    # 开发环境下也输出到 stderr，确保能看到
    if settings.is_development:
        print("=" * 80, file=sys.stderr)
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        print("=" * 80, file=sys.stderr)

    return _error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        message="Internal server error",
        code="INTERNAL_ERROR",
    )


# =============================================================================
# API 路由
# =============================================================================

# 注册各领域的 API 路由
api_router_prefix = "/api/v1"

# 认证相关路由
app.include_router(identity_router, prefix=f"{api_router_prefix}/auth", tags=["Authentication"])

# API Key 管理
app.include_router(api_key_router, prefix=f"{api_router_prefix}/api-keys", tags=["API Keys"])

# Agent 管理
app.include_router(agent_router, prefix=f"{api_router_prefix}/agents", tags=["Agents"])

# 会话管理
app.include_router(session_router, prefix=f"{api_router_prefix}/sessions", tags=["Sessions"])

# 对话接口
app.include_router(chat_router, prefix=api_router_prefix, tags=["Chat"])

# 工具管理
app.include_router(tools_router, prefix=api_router_prefix, tags=["Tools"])

# 记忆管理
app.include_router(memory_router, prefix=f"{api_router_prefix}/memory", tags=["Memory"])

# 系统接口
app.include_router(system_router, prefix=f"{api_router_prefix}/system", tags=["System"])

# 评估接口
app.include_router(evaluation_router, prefix=api_router_prefix, tags=["Evaluation"])

# 执行配置
app.include_router(execution_router, prefix=api_router_prefix, tags=["Execution"])

# MCP 管理（管理 API：/servers, /templates 等）
app.include_router(mcp_router, prefix=f"{api_router_prefix}/mcp", tags=["MCP Management"])
# MCP Streamable HTTP（llm-server 等：/, /{server_name}, /{server_name}/info）
app.include_router(mcp_server_router, prefix=f"{api_router_prefix}/mcp", tags=["MCP Server"])
# 同时挂载 /mcp，便于 Cursor 等客户端使用 http://localhost:8000/mcp/llm-server
app.include_router(mcp_server_router, prefix="/mcp", tags=["MCP Server"])

# 用量与配额
app.include_router(
    usage_router,
    prefix=f"{api_router_prefix}/usage",
    tags=["Usage"],
)

# 视频生成任务
app.include_router(
    video_task_router,
    prefix=f"{api_router_prefix}/video-tasks",
    tags=["Video Tasks"],
)

# Listing Studio 工作流（原 product-info）
app.include_router(
    listing_studio_router,
    prefix=f"{api_router_prefix}/listing-studio",
    tags=["Listing Studio"],
)

# 平台管理 - 对象存储
app.include_router(
    admin_storage_router,
    prefix=f"{api_router_prefix}/admin/storage",
    tags=["Admin Storage"],
)

# 兼容旧路径 /product-info（带 Deprecation 响应头）
app.include_router(
    product_info_router,
    prefix=f"{api_router_prefix}/product-info",
    tags=["Product Info (deprecated)"],
)

# AI Gateway 团队 API（/api/v1/gateway/teams*，由 tenancy 域实现）
app.include_router(
    tenancy_teams_router,
    prefix=f"{api_router_prefix}/gateway",
    tags=["Tenancy / Teams"],
)

# AI Gateway 管理 API：/api/v1/gateway/*
app.include_router(gateway_mgmt_router, tags=["AI Gateway"])

# AI Gateway OpenAI 兼容入口：根路径下的 /v1/*（与 OpenAI 客户端默认 base_url 一致）
app.include_router(openai_compat_router, tags=["OpenAI Compat"])
# Anthropic Messages API：/v1/messages（与 Anthropic SDK base_url 对齐）
app.include_router(anthropic_compat_router, tags=["Anthropic Compat"])


@app.get("/")
async def root() -> dict[str, str]:
    """根端点"""
    return {
        "message": "AI Agent API",
        "version": "0.1.0",
        "docs": "/docs",
    }


@app.get("/health")
async def health() -> dict[str, str]:
    """健康检查"""
    return {"status": "healthy"}
