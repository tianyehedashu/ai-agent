"""
可观测性中间件 (Observability Middleware)

提供统一的错误上报、监控告警等跨切面逻辑。
不处理异常响应（由 FastAPI exception_handler 处理），专注于观察性数据收集。
"""

import time
from typing import Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from libs.observability.sentry import (
    add_breadcrumb,
    capture_exception,
    is_sentry_initialized,
    set_tag,
    set_user_context,
)
from utils.logging import get_logger

logger = get_logger(__name__)


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """可观测性中间件

    功能：
    1. 记录请求上下文到 Sentry（面包屑）
    2. 收集和上报指标（响应时间、状态码分布）
    3. 关联用户上下文到 Sentry 事件
    4. 记录异常到 Sentry

    注意：此中间件不处理异常响应，仅负责观察性数据收集。
    """

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        """处理请求并收集观察性数据"""
        start_time = time.time()

        # 获取 Trace ID
        trace_id = getattr(request.state, "trace_id", None)
        if trace_id:
            set_tag("trace_id", trace_id)

        # 设置用户上下文（如果有认证用户）
        self._set_user_context(request)

        # 添加请求面包屑
        self._add_request_breadcrumb(request)

        # 处理请求
        response = await call_next(request)

        # 计算耗时
        duration_ms = (time.time() - start_time) * 1000

        # 收集指标
        self._collect_metrics(request, response, duration_ms)

        return response

    def _set_user_context(self, request: Request) -> None:
        """设置用户上下文到 Sentry"""
        if not is_sentry_initialized():
            return

        # 尝试从 request.state 获取用户信息
        user = getattr(request.state, "user", None)
        if user:
            user_id = getattr(user, "id", None)
            if user_id:
                email = getattr(user, "email", None)
                set_user_context(
                    user_id=str(user_id),
                    email=email,
                    username=getattr(user, "username", None),
                )

        # 匿名用户
        anonymous_id = getattr(request.state, "anonymous_user_id", None)
        if anonymous_id:
            set_user_context(user_id=f"anonymous:{anonymous_id}")

    def _add_request_breadcrumb(self, request: Request) -> None:
        """添加请求面包屑到 Sentry"""
        if not is_sentry_initialized():
            return

        add_breadcrumb(
            message=f"{request.method} {request.url.path}",
            category="http",
            level="info",
            data={
                "method": request.method,
                "path": request.url.path,
                "query_params": str(request.url.query) if request.url.query else None,
                "user_agent": request.headers.get("User-Agent"),
            },
        )

    def _collect_metrics(
        self,
        request: Request,
        response: Response,
        duration_ms: float,
    ) -> None:
        """收集指标"""
        if not is_sentry_initialized():
            return

        # 设置响应相关标签
        set_tag("status_code", response.status_code)
        set_tag("method", request.method)

        # 记录慢请求
        if duration_ms > 1000:  # 超过 1 秒
            add_breadcrumb(
                message=f"Slow request: {request.method} {request.url.path}",
                category="performance",
                level="warning",
                data={
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": round(duration_ms, 2),
                },
            )

        # 记录错误响应
        if response.status_code >= 500:
            add_breadcrumb(
                message=f"Server error: {request.method} {request.url.path}",
                category="error",
                level="error",
                data={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                },
            )


def report_exception(
    exception: Exception,
    request: Request | None = None,
    **tags: str,
) -> str | None:
    """上报异常到 Sentry

    Args:
        exception: 异常对象
        request: 可选的请求对象
        **tags: 自定义标签

    Returns:
        Sentry 事件 ID
    """
    if request:
        # 添加请求相关标签
        tags["method"] = request.method
        tags["path"] = request.url.path

    return capture_exception(exception, **tags)
