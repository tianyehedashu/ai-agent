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
import warnings

# Windows 需要使用 SelectorEventLoop（psycopg 异步要求）。
# 注意：此 policy 设置只对 pytest / 直接 ``python -m`` 等"以本模块为入口"的
# 场景兜底——它们通常用 ``asyncio.run()``，会读取此 policy。
#
# 对 uvicorn 入口此设置**无效**：uvicorn ≥ 0.40 通过
# ``asyncio.Runner(loop_factory=...)`` 创建循环，完全绕过 policy。uvicorn
# 入口必须由启动器（``scripts/run_server.py`` / ``scripts/run_dev_server.py``）
# 给 ``uvicorn.run`` 传 ``loop="bootstrap.event_loop:selector_event_loop_factory"``。
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# pylint: disable=wrong-import-position
# 这些导入必须在事件循环设置之后，以确保 Windows 平台上的异步操作正常工作
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.responses import RedirectResponse

from bootstrap.config import settings
from domains.agent.application.listing_studio_local_image_for_gateway import (
    listing_studio_local_image_port_for_session,
)
from domains.agent.application.startup import (
    agent_streamable_http_lifespan,
    run_agent_shutdown,
    run_agent_startup,
)
from domains.agent.presentation.admin_storage_router import router as admin_storage_router

# 从各领域的 presentation 层导入路由
from domains.agent.presentation.agent_router import router as agent_router
from domains.agent.presentation.chat_router import router as chat_router
from domains.agent.presentation.execution_router import router as execution_router
from domains.agent.presentation.listing_studio_router import router as listing_studio_router
from domains.agent.presentation.mcp_router import router as mcp_router
from domains.agent.presentation.mcp_server_router import router as mcp_server_router
from domains.agent.presentation.memory_router import router as memory_router
from domains.agent.presentation.product_info_router import router as product_info_router
from domains.agent.presentation.system_router import router as system_router
from domains.agent.presentation.tools_router import router as tools_router
from domains.agent.presentation.video_task_router import router as video_task_router
from domains.evaluation.presentation.router import router as evaluation_router
from domains.gateway.application.listing_studio_image_port_registry import (
    register_listing_studio_local_image_port_factory,
)
from domains.gateway.application.startup import run_gateway_shutdown, run_gateway_startup
from domains.gateway.presentation.anthropic_compat_router import router as anthropic_compat_router
from domains.gateway.presentation.management_router import router as gateway_mgmt_router
from domains.gateway.presentation.openai_compat_router import router as openai_compat_router
from domains.gateway.presentation.platform_api_key_usage_middleware import (
    PlatformApiKeyUsageASGIMiddleware,
)
from domains.identity.infrastructure.auth.jwt import init_jwt_manager
from domains.identity.presentation.admin_users_router import router as admin_users_router
from domains.identity.presentation.api_key_router import router as api_key_router
from domains.identity.presentation.router import router as identity_router
from domains.identity.presentation.usage_router import router as usage_router
from domains.session.presentation import session_router
from domains.tenancy.presentation.teams_router import router as tenancy_teams_router
from libs.api.paths import anthropic_compat_base, api_v1_path, openai_compat_base, service_path
from libs.api.problem_details import (
    problem_response_from_agent_error,
    problem_response_from_http_mappable,
    problem_response_from_request_validation,
    problem_response_internal,
)
from libs.background_tasks import init_background_tasks, shutdown_app_background_tasks
from libs.db.database import init_db
from libs.db.redis import close_redis, init_redis
from libs.exceptions import (
    AIAgentError,
    AuthenticationError,
    CheckpointError,
    ConflictError,
    ExternalServiceError,
    HttpMappableDomainError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    TokenError,
    ToolExecutionError,
    ValidationError,
)
from libs.exceptions.codes import INTERNAL_ERROR
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
    register_listing_studio_local_image_port_factory(listing_studio_local_image_port_for_session)

    # 初始化 Redis（开发机未起 redis 时仅告警，不阻断启动）
    try:
        await init_redis()
    except Exception as e:
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
        "X-Gateway-Preflight-Ms",
        "X-Gateway-Upstream-Ms",
    ],
)

# 纯 ASGI 中间件（与 SSE/StreamingResponse 兼容；勿改用 @app.middleware + BaseHTTPMiddleware）
app.add_middleware(PermissionContextASGIMiddleware)
app.add_middleware(PlatformApiKeyUsageASGIMiddleware)
app.add_middleware(AnonymousCookieASGIMiddleware)


# =============================================================================
# 全局异常处理器（RFC 7807 Problem Details）
# =============================================================================


@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    logger.warning("Request validation error: %s", exc.errors())
    return problem_response_from_request_validation(request, exc)


@app.exception_handler(HttpMappableDomainError)
async def http_mappable_domain_error_handler(
    request: Request,
    exc: HttpMappableDomainError,
) -> JSONResponse:
    logger.warning("Domain error: %s", exc)
    return problem_response_from_http_mappable(request, exc)


@app.exception_handler(ValidationError)
async def validation_error_handler(
    request: Request,
    exc: ValidationError,
) -> JSONResponse:
    logger.warning("Validation error: %s", exc.message)
    return problem_response_from_agent_error(request, exc, status.HTTP_400_BAD_REQUEST)


@app.exception_handler(NotFoundError)
async def not_found_error_handler(
    request: Request,
    exc: NotFoundError,
) -> JSONResponse:
    logger.warning("Resource not found: %s", exc.message)
    return problem_response_from_agent_error(request, exc, status.HTTP_404_NOT_FOUND)


@app.exception_handler(PermissionDeniedError)
async def permission_denied_error_handler(
    request: Request,
    exc: PermissionDeniedError,
) -> JSONResponse:
    logger.warning("Permission denied: %s", exc.message)
    return problem_response_from_agent_error(request, exc, status.HTTP_403_FORBIDDEN)


@app.exception_handler(AuthenticationError)
async def authentication_error_handler(
    request: Request,
    exc: AuthenticationError,
) -> JSONResponse:
    logger.warning("Authentication failed: %s", exc.message)
    return problem_response_from_agent_error(
        request,
        exc,
        status.HTTP_401_UNAUTHORIZED,
        headers={"WWW-Authenticate": "Bearer"},
    )


@app.exception_handler(TokenError)
async def token_error_handler(
    request: Request,
    exc: TokenError,
) -> JSONResponse:
    logger.warning("Token error: %s", exc.message)
    return problem_response_from_agent_error(
        request,
        exc,
        status.HTTP_401_UNAUTHORIZED,
        headers={"WWW-Authenticate": "Bearer"},
    )


@app.exception_handler(ConflictError)
async def conflict_error_handler(
    request: Request,
    exc: ConflictError,
) -> JSONResponse:
    logger.warning("Resource conflict: %s", exc.message)
    return problem_response_from_agent_error(request, exc, status.HTTP_409_CONFLICT)


@app.exception_handler(RateLimitError)
async def rate_limit_error_handler(
    request: Request,
    exc: RateLimitError,
) -> JSONResponse:
    logger.warning("Rate limit exceeded: %s", exc.message)
    headers = {"Retry-After": str(exc.retry_after)} if exc.retry_after else None
    return problem_response_from_agent_error(
        request,
        exc,
        status.HTTP_429_TOO_MANY_REQUESTS,
        headers=headers,
    )


@app.exception_handler(ExternalServiceError)
async def external_service_error_handler(
    request: Request,
    exc: ExternalServiceError,
) -> JSONResponse:
    logger.error("External service error: %s - %s", exc.service, exc.message)
    return problem_response_from_agent_error(request, exc, status.HTTP_502_BAD_GATEWAY)


@app.exception_handler(ToolExecutionError)
async def tool_execution_error_handler(
    request: Request,
    exc: ToolExecutionError,
) -> JSONResponse:
    logger.error("Tool execution error: %s - %s", exc.tool_name, exc.message)
    return problem_response_from_agent_error(request, exc, status.HTTP_500_INTERNAL_SERVER_ERROR)


@app.exception_handler(CheckpointError)
async def checkpoint_error_handler(
    request: Request,
    exc: CheckpointError,
) -> JSONResponse:
    logger.error("Checkpoint error: %s", exc.message)
    return problem_response_from_agent_error(request, exc, status.HTTP_500_INTERNAL_SERVER_ERROR)


@app.exception_handler(AIAgentError)
async def ai_agent_error_handler(
    request: Request,
    exc: AIAgentError,
) -> JSONResponse:
    logger.error("AI Agent error: %s", exc.message)
    return problem_response_from_agent_error(request, exc, status.HTTP_500_INTERNAL_SERVER_ERROR)


@app.exception_handler(Exception)
async def general_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """处理未捕获的异常"""
    logger.exception("Unhandled exception: %s", exc)

    if settings.is_development:
        print("=" * 80, file=sys.stderr)
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        print("=" * 80, file=sys.stderr)

    return problem_response_internal(request, code=INTERNAL_ERROR)


# =============================================================================
# API 路由
# =============================================================================

api_router_prefix = api_v1_path()

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

# 平台管理 - 用户角色
app.include_router(
    admin_users_router,
    prefix=f"{api_router_prefix}/admin/users",
    tags=["Admin Users"],
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

# AI Gateway 管理 API：{ROOT}/api/v1/gateway/*
app.include_router(
    gateway_mgmt_router,
    prefix=f"{api_router_prefix}/gateway",
    tags=["AI Gateway"],
)

# AI Gateway OpenAI 兼容入口：{ROOT}/api/v1/openai/v1/*
app.include_router(
    openai_compat_router,
    prefix=api_v1_path("openai"),
    tags=["OpenAI Compat"],
)
# Anthropic Messages API：{ROOT}/api/v1/anthropic/v1/messages
app.include_router(
    anthropic_compat_router,
    prefix=api_v1_path("anthropic"),
    tags=["Anthropic Compat"],
)


@app.get(service_path())
async def root() -> dict[str, str]:
    """根端点"""
    return {
        "message": "AI Agent API",
        "version": "0.1.0",
        "docs": "/docs",
    }


@app.get(service_path("health"))
async def health() -> dict[str, str]:
    """健康检查"""
    return {"status": "healthy"}


# Docker 本地探针：ROOT_PATH 非空时保留根级 /health
if settings.root_path.strip("/"):

    @app.get("/health")
    async def health_root_alias() -> dict[str, str]:
        """健康检查（无服务前缀别名，便于容器内 curl localhost:8000/health）"""
        return {"status": "healthy"}


# 开发/无 ROOT_PATH：根级 /v1/* 301 重定向至新兼容面（一个版本周期过渡）
if not settings.root_path.strip("/"):

    @app.api_route(
        "/v1/{path:path}",
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
        include_in_schema=False,
    )
    async def legacy_v1_redirect(path: str, request: Request) -> RedirectResponse:
        if path == "messages" or path.startswith("messages/"):
            target = f"{anthropic_compat_base()}/v1/{path}"
        else:
            target = f"{openai_compat_base()}/{path}"
        if request.url.query:
            target = f"{target}?{request.url.query}"
        return RedirectResponse(url=target, status_code=301)
