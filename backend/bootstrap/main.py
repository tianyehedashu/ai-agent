"""
AI Agent Backend - Main Application

FastAPI 应用入口点
"""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
import os
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
from domains.agent.infrastructure.engine.langgraph_checkpointer import LangGraphCheckpointer
from domains.agent.infrastructure.sandbox import SessionManager

# 从各领域的 presentation 层导入路由
from domains.agent.presentation.agent_router import router as agent_router
from domains.agent.presentation.chat_router import router as chat_router
from domains.agent.presentation.execution_router import router as execution_router
from domains.agent.presentation.mcp_router import router as mcp_router
from domains.agent.presentation.memory_router import router as memory_router
from domains.agent.presentation.session_router import router as session_router
from domains.agent.presentation.system_router import router as system_router
from domains.agent.presentation.tools_router import router as tools_router
from domains.evaluation.presentation.router import router as evaluation_router
from domains.identity.infrastructure.auth.jwt import init_jwt_manager
from domains.identity.presentation.router import router as identity_router
from domains.studio.presentation.quality_router import router as quality_router
from domains.studio.presentation.router import router as studio_router
from exceptions import (
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
from libs.db.database import init_db
from libs.db.redis import close_redis, init_redis
from libs.middleware.permission import PermissionContextMiddleware
from utils.logging import get_logger, setup_logging

# pylint: enable=wrong-import-position

logger = get_logger(__name__)


def _setup_litellm_env() -> None:
    """设置 LiteLLM 所需的环境变量"""
    # LiteLLM 需要环境变量来识别某些提供商
    # 这些环境变量在应用启动时设置，确保所有实例都能使用
    if settings.deepseek_api_key and "DEEPSEEK_API_KEY" not in os.environ:
        os.environ["DEEPSEEK_API_KEY"] = settings.deepseek_api_key.get_secret_value()
    if settings.volcengine_api_key and "VOLCENGINE_API_KEY" not in os.environ:
        os.environ["VOLCENGINE_API_KEY"] = settings.volcengine_api_key.get_secret_value()
    if settings.dashscope_api_key and "DASHSCOPE_API_KEY" not in os.environ:
        os.environ["DASHSCOPE_API_KEY"] = settings.dashscope_api_key.get_secret_value()
    if settings.zhipuai_api_key:
        # LiteLLM 使用 ZAI_API_KEY 环境变量
        if "ZAI_API_KEY" not in os.environ:
            os.environ["ZAI_API_KEY"] = settings.zhipuai_api_key.get_secret_value()
        # 同时设置 ZHIPUAI_API_KEY 以保持兼容性
        if "ZHIPUAI_API_KEY" not in os.environ:
            os.environ["ZHIPUAI_API_KEY"] = settings.zhipuai_api_key.get_secret_value()


@asynccontextmanager
async def lifespan(_fastapi_app: FastAPI) -> AsyncGenerator[None, None]:
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
    _setup_litellm_env()

    # 初始化数据库
    await init_db()

    # 初始化 Redis
    try:
        await init_redis()
    except (ConnectionError, OSError) as e:
        logger.warning("Redis not available: %s", e)

    # 初始化全局 checkpointer（在应用启动时创建并 setup）
    try:
        global_checkpointer = LangGraphCheckpointer(storage_type="postgres")
        await global_checkpointer.setup()
        # 将全局 checkpointer 保存到应用状态中
        _fastapi_app.state.checkpointer = global_checkpointer
        logger.info("Global checkpointer initialized and setup completed")
    except Exception as e:
        logger.error("Failed to initialize global checkpointer: %s", e, exc_info=True)
        # 如果初始化失败，使用 MemorySaver 作为后备
        global_checkpointer = LangGraphCheckpointer(storage_type="memory")
        await global_checkpointer.setup()
        _fastapi_app.state.checkpointer = global_checkpointer
        logger.warning("Using MemorySaver as fallback for checkpointer")

    # 清理孤儿容器（上次异常关闭遗留的）
    # 在初始化 SessionManager 之前清理，避免冲突
    try:
        from domains.agent.infrastructure.sandbox.executor import (  # pylint: disable=import-outside-toplevel
            SessionDockerExecutor,
        )

        orphans = await SessionDockerExecutor.cleanup_orphaned_containers(
            max_age_seconds=300  # 清理超过 5 分钟的孤儿容器
        )
        if orphans:
            logger.info(
                "Cleaned up %d orphaned containers on startup: %s",
                len(orphans),
                orphans,
            )
    except Exception as e:
        # 清理失败不应阻止应用启动
        logger.warning("Failed to cleanup orphaned containers: %s", e)

    # 初始化并启动会话管理器
    session_manager = SessionManager.get_instance()
    await session_manager.start()
    _fastapi_app.state.session_manager = session_manager
    logger.info("SessionManager started")

    # 初始化默认系统级 MCP 服务器
    try:
        from domains.agent.application.mcp_init import (
            init_default_mcp_servers,  # pylint: disable=import-outside-toplevel
        )

        await init_default_mcp_servers()
        logger.info("Default MCP servers initialization completed")
    except Exception as e:
        # 初始化失败不应阻止应用启动
        logger.warning("Failed to initialize default MCP servers: %s", e)

    yield

    # 关闭时
    # 停止会话管理器（会清理所有会话容器）
    if hasattr(_fastapi_app.state, "session_manager"):
        await _fastapi_app.state.session_manager.stop()
        logger.info("SessionManager stopped")

    # 清理 LiteLLM 异步客户端
    try:
        import litellm  # pylint: disable=import-outside-toplevel

        if hasattr(litellm, "close_litellm_async_clients"):
            # close_litellm_async_clients 是一个协程，需要 await
            await litellm.close_litellm_async_clients()
            logger.info("LiteLLM async clients closed successfully")
    except Exception as e:
        logger.warning("Error closing LiteLLM async clients: %s", e)

    # 清理 checkpointer
    if hasattr(_fastapi_app.state, "checkpointer"):
        try:
            await _fastapi_app.state.checkpointer.cleanup()
        except Exception as e:
            logger.warning("Error cleaning up checkpointer: %s", e)

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
)

# 权限上下文中间件（在认证依赖之后设置权限上下文）
app.add_middleware(PermissionContextMiddleware)


# =============================================================================
# 匿名用户 Cookie 中间件
# =============================================================================

# 匿名用户 Cookie 配置
ANONYMOUS_USER_COOKIE = "anonymous_user_id"
ANONYMOUS_COOKIE_MAX_AGE = 365 * 24 * 60 * 60  # 1 年


@app.middleware("http")
async def anonymous_user_cookie_middleware(request: Request, call_next):
    """为匿名用户设置持久化 Cookie

    当检测到新的匿名用户（request.state.anonymous_user_id 存在）时，
    在响应中设置 Cookie 以便后续请求能够识别同一用户。
    """
    response = await call_next(request)

    # 检查是否需要设置匿名用户 Cookie
    if hasattr(request.state, "anonymous_user_id"):
        anonymous_id = request.state.anonymous_user_id
        # 设置持久化 Cookie（1 年有效期）
        response.set_cookie(
            key=ANONYMOUS_USER_COOKIE,
            value=anonymous_id,
            max_age=ANONYMOUS_COOKIE_MAX_AGE,
            path="/",  # 确保 Cookie 对所有路径有效
            httponly=True,  # 防止 XSS 攻击
            samesite="lax",  # 防止 CSRF 攻击，但允许顶级导航
            secure=not settings.is_development,  # 生产环境要求 HTTPS
        )

    return response


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

# 工作台 (Studio)
app.include_router(studio_router, prefix=api_router_prefix, tags=["Studio"])

# 代码质量
app.include_router(quality_router, prefix=api_router_prefix, tags=["Quality"])

# 系统接口
app.include_router(system_router, prefix=f"{api_router_prefix}/system", tags=["System"])

# 评估接口
app.include_router(evaluation_router, prefix=api_router_prefix, tags=["Evaluation"])

# 执行配置
app.include_router(execution_router, prefix=api_router_prefix, tags=["Execution"])

# MCP 管理
app.include_router(mcp_router, prefix=f"{api_router_prefix}/mcp", tags=["MCP Management"])


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
