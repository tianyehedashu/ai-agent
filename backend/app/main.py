"""
AI Agent Backend - Main Application

FastAPI 应用入口点
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.v1.router import api_router
from app.config import settings
from db.database import init_db
from db.redis import close_redis, init_redis
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
from utils.logging import get_logger, setup_logging

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_fastapi_app: FastAPI) -> AsyncGenerator[None, None]:
    """应用生命周期管理"""
    # 启动时
    setup_logging()

    # 初始化数据库
    await init_db()

    # 初始化 Redis
    try:
        await init_redis()
    except (ConnectionError, OSError) as e:
        logger.warning("Redis not available: %s", e)

    yield

    # 关闭时
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.debug else settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    logger.exception("Unhandled exception: %s", exc)
    return _error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        message="Internal server error",
        code="INTERNAL_ERROR",
    )


# =============================================================================
# API 路由
# =============================================================================

# 注册 API 路由
app.include_router(api_router, prefix="/api/v1")


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
