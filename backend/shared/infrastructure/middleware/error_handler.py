"""
错误处理中间件

统一处理异常和错误
"""

from typing import Any

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from exceptions import AIAgentError
from utils.logging import get_logger

logger = get_logger(__name__)


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """错误处理中间件"""

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        """处理请求"""
        try:
            return await call_next(request)
        except AIAgentError as e:
            # 已知的业务异常
            logger.warning("Business error: %s", e.message)
            return JSONResponse(
                status_code=e.status_code,
                content={
                    "detail": e.message,
                    "code": e.code,
                },
            )
        except Exception as e:
            # 未知异常
            logger.exception("Unhandled exception: %s", e)
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "detail": "Internal server error",
                    "code": "INTERNAL_ERROR",
                },
            )
