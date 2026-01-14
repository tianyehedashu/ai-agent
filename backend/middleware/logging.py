"""
日志中间件

记录请求和响应日志
"""

import time
from typing import Any

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from utils.logging import get_logger

logger = get_logger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """日志中间件"""

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        """处理请求"""
        start_time = time.time()

        # 记录请求
        logger.info(
            "Request: %s %s",
            request.method,
            request.url.path,
            extra={
                "method": request.method,
                "path": request.url.path,
                "client": request.client.host if request.client else None,
            },
        )

        # 处理请求
        response = await call_next(request)

        # 计算耗时
        duration_ms = (time.time() - start_time) * 1000

        # 记录响应
        logger.info(
            "Response: %s %s - %d (%dms)",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )

        return response
