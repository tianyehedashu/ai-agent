"""
分布式追踪

实现执行链路追踪，支持时间旅行调试
"""

import time
from typing import Any
from uuid import uuid4

from utils.logging import get_logger

logger = get_logger(__name__)


class Span:
    """追踪跨度"""

    def __init__(
        self,
        span_id: str,
        trace_id: str,
        name: str,
        parent_id: str | None = None,
    ) -> None:
        self.span_id = span_id
        self.trace_id = trace_id
        self.name = name
        self.parent_id = parent_id
        self.start_time = time.time()
        self.end_time: float | None = None
        self.tags: dict[str, Any] = {}
        self.logs: list[dict[str, Any]] = []

    def finish(self) -> None:
        """结束跨度"""
        self.end_time = time.time()

    def add_tag(self, key: str, value: Any) -> None:
        """添加标签"""
        self.tags[key] = value

    def add_log(self, message: str, level: str = "info", **kwargs: Any) -> None:
        """添加日志"""
        self.logs.append(
            {
                "message": message,
                "level": level,
                "timestamp": time.time(),
                **kwargs,
            }
        )

    @property
    def duration_ms(self) -> float:
        """持续时间（毫秒）"""
        if self.end_time:
            return (self.end_time - self.start_time) * 1000
        return (time.time() - self.start_time) * 1000


class TraceCollector:
    """
    追踪收集器

    收集和管理执行链路追踪信息
    """

    def __init__(self) -> None:
        self._traces: dict[str, list[Span]] = {}
        self._active_spans: dict[str, Span] = {}

    def start_trace(self, trace_id: str | None = None) -> str:
        """
        开始追踪

        Args:
            trace_id: 追踪 ID，如果为 None 则自动生成

        Returns:
            str: 追踪 ID
        """
        if trace_id is None:
            trace_id = str(uuid4())

        self._traces[trace_id] = []
        return trace_id

    def start_span(
        self,
        trace_id: str,
        name: str,
        parent_id: str | None = None,
    ) -> Span:
        """
        开始跨度

        Args:
            trace_id: 追踪 ID
            name: 跨度名称
            parent_id: 父跨度 ID

        Returns:
            Span: 跨度对象
        """
        span_id = str(uuid4())
        span = Span(span_id, trace_id, name, parent_id)

        if trace_id not in self._traces:
            self._traces[trace_id] = []

        self._traces[trace_id].append(span)
        self._active_spans[span_id] = span

        return span

    def finish_span(self, span_id: str) -> None:
        """
        结束跨度

        Args:
            span_id: 跨度 ID
        """
        if span_id in self._active_spans:
            span = self._active_spans[span_id]
            span.finish()
            del self._active_spans[span_id]

    def get_trace(self, trace_id: str) -> list[Span]:
        """
        获取追踪信息

        Args:
            trace_id: 追踪 ID

        Returns:
            list[Span]: 跨度列表
        """
        return self._traces.get(trace_id, [])

    def get_span(self, span_id: str) -> Span | None:
        """
        获取跨度

        Args:
            span_id: 跨度 ID

        Returns:
            Span | None: 跨度对象
        """
        return self._active_spans.get(span_id)

    def export_trace(self, trace_id: str) -> dict[str, Any]:
        """
        导出追踪信息（用于可视化）

        Args:
            trace_id: 追踪 ID

        Returns:
            dict: 追踪信息
        """
        spans = self.get_trace(trace_id)
        return {
            "trace_id": trace_id,
            "spans": [
                {
                    "span_id": span.span_id,
                    "name": span.name,
                    "parent_id": span.parent_id,
                    "start_time": span.start_time,
                    "end_time": span.end_time,
                    "duration_ms": span.duration_ms,
                    "tags": span.tags,
                    "logs": span.logs,
                }
                for span in spans
            ],
        }
