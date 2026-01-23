"""
限流中间件

实现请求速率限制
"""

from collections import defaultdict
import time
from typing import Any

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from utils.logging import get_logger

logger = get_logger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """限流中间件"""

    def __init__(
        self,
        app: Any,
        requests_per_minute: int = 60,
        requests_per_hour: int = 1000,
    ) -> None:
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self._minute_requests: dict[str, list[float]] = defaultdict(list)
        self._hour_requests: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        """处理请求"""
        # 获取客户端标识
        client_id = request.client.host if request.client else "unknown"
        user_id = getattr(request.state, "user_id", None)
        identifier = user_id or client_id

        current_time = time.time()

        # 清理过期记录
        self._cleanup_old_requests(identifier, current_time)

        # 检查分钟限制
        minute_requests = self._minute_requests[identifier]
        if len(minute_requests) >= self.requests_per_minute:
            logger.warning("Rate limit exceeded (per minute) for %s", identifier)
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": "Rate limit exceeded",
                    "retry_after": 60,
                },
                headers={"Retry-After": "60"},
            )

        # 检查小时限制
        hour_requests = self._hour_requests[identifier]
        if len(hour_requests) >= self.requests_per_hour:
            logger.warning("Rate limit exceeded (per hour) for %s", identifier)
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": "Rate limit exceeded",
                    "retry_after": 3600,
                },
                headers={"Retry-After": "3600"},
            )

        # 记录请求
        minute_requests.append(current_time)
        hour_requests.append(current_time)

        return await call_next(request)

    def _cleanup_old_requests(self, identifier: str, current_time: float) -> None:
        """清理过期请求记录"""
        # 清理1分钟前的记录
        minute_requests = self._minute_requests[identifier]
        self._minute_requests[identifier] = [t for t in minute_requests if current_time - t < 60]

        # 清理1小时前的记录
        hour_requests = self._hour_requests[identifier]
        self._hour_requests[identifier] = [t for t in hour_requests if current_time - t < 3600]
