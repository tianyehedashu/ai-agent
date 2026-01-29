"""
Trace ID Middleware - 分布式追踪中间件

为每个请求生成唯一的 Trace ID，并注入到日志上下文中。
Trace ID 贯穿整个请求生命周期，便于日志追踪和问题排查。
"""

from collections.abc import Callable
import uuid

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from utils.logging import clear_trace_context, get_logger, set_trace_context

logger = get_logger(__name__)


class TraceIdMiddleware(BaseHTTPMiddleware):
    """Trace ID 中间件

    功能：
    1. 从请求头读取或生成新的 Trace ID
    2. 将 Trace ID 注入到日志上下文
    3. 在响应头返回 Trace ID
    4. 请求结束后清理上下文
    """

    def __init__(
        self,
        app: ASGIApp,
        header_name: str = "X-Trace-ID",
        generate_if_missing: bool = True,
    ) -> None:
        """
        Args:
            app: ASGI 应用
            header_name: Trace ID 请求头名称
            generate_if_missing: 请求头中不存在时是否生成新的 Trace ID
        """
        super().__init__(app)
        self.header_name = header_name
        self.generate_if_missing = generate_if_missing

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求，注入 Trace ID"""
        # 尝试从请求头获取 Trace ID
        trace_id = request.headers.get(self.header_name, "")

        # 如果不存在且配置了自动生成，则创建新的 Trace ID
        if not trace_id and self.generate_if_missing:
            trace_id = str(uuid.uuid4())

        # 注入到日志上下文
        set_trace_context(trace_id=trace_id)

        # 存储到 request.state，供后续使用
        request.state.trace_id = trace_id

        # 调用下一个中间件/路由
        response = await call_next(request)

        # 在响应头中返回 Trace ID
        if trace_id:
            response.headers[self.header_name] = trace_id

        # 清理日志上下文
        clear_trace_context()

        return response


async def get_trace_id(request: Request) -> str | None:
    """从请求中获取 Trace ID

    Args:
        request: FastAPI 请求对象

    Returns:
        Trace ID 字符串，如果不存在则返回 None
    """
    return getattr(request.state, "trace_id", None)


def get_trace_id_from_headers(request: Request, header_name: str = "X-Trace-ID") -> str | None:
    """从请求头中获取 Trace ID

    Args:
        request: FastAPI 请求对象
        header_name: 请求头名称

    Returns:
        Trace ID 字符串，如果不存在则返回 None
    """
    return request.headers.get(header_name)
