"""
指标收集

收集系统指标和业务指标
"""

from collections import defaultdict
import time
from typing import Any

from utils.logging import get_logger

logger = get_logger(__name__)


class MetricsCollector:
    """
    指标收集器

    收集和管理系统指标
    """

    def __init__(self) -> None:
        self._counters: dict[str, int] = defaultdict(int)
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = defaultdict(list)
        self._timers: dict[str, list[float]] = defaultdict(list)

    def increment(
        self, metric_name: str, value: int = 1, tags: dict[str, str] | None = None
    ) -> None:
        """
        增加计数器

        Args:
            metric_name: 指标名称
            value: 增加值
            tags: 标签（暂未使用）
        """
        self._counters[metric_name] += value

    def set_gauge(self, metric_name: str, value: float, tags: dict[str, str] | None = None) -> None:
        """
        设置仪表值

        Args:
            metric_name: 指标名称
            value: 值
            tags: 标签（暂未使用）
        """
        self._gauges[metric_name] = value

    def record_histogram(
        self, metric_name: str, value: float, tags: dict[str, str] | None = None
    ) -> None:
        """
        记录直方图值

        Args:
            metric_name: 指标名称
            value: 值
            tags: 标签（暂未使用）
        """
        self._histograms[metric_name].append(value)

    def record_timer(
        self, metric_name: str, duration_ms: float, tags: dict[str, str] | None = None
    ) -> None:
        """
        记录计时器值

        Args:
            metric_name: 指标名称
            duration_ms: 持续时间（毫秒）
            tags: 标签（暂未使用）
        """
        self._timers[metric_name].append(duration_ms)

    def get_counter(self, metric_name: str) -> int:
        """获取计数器值"""
        return self._counters.get(metric_name, 0)

    def get_gauge(self, metric_name: str) -> float | None:
        """获取仪表值"""
        return self._gauges.get(metric_name)

    def get_histogram_stats(self, metric_name: str) -> dict[str, float] | None:
        """获取直方图统计"""
        values = self._histograms.get(metric_name)
        if not values:
            return None

        return {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
            "p50": sorted(values)[len(values) // 2],
            "p95": sorted(values)[int(len(values) * 0.95)],
            "p99": sorted(values)[int(len(values) * 0.99)],
        }

    def get_timer_stats(self, metric_name: str) -> dict[str, float] | None:
        """获取计时器统计"""
        return self.get_histogram_stats(metric_name)

    def export_metrics(self) -> dict[str, Any]:
        """
        导出所有指标（用于监控系统）

        Returns:
            dict: 指标数据
        """
        return {
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "histograms": {name: self.get_histogram_stats(name) for name in self._histograms},
            "timers": {name: self.get_timer_stats(name) for name in self._timers},
        }

    def reset(self) -> None:
        """重置所有指标"""
        self._counters.clear()
        self._gauges.clear()
        self._histograms.clear()
        self._timers.clear()


class Timer:
    """计时器上下文管理器"""

    def __init__(
        self, collector: MetricsCollector, metric_name: str, tags: dict[str, str] | None = None
    ) -> None:
        self.collector = collector
        self.metric_name = metric_name
        self.tags = tags
        self.start_time: float | None = None

    def __enter__(self) -> "Timer":
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self.start_time:
            duration_ms = (time.time() - self.start_time) * 1000
            self.collector.record_timer(self.metric_name, duration_ms, self.tags)
