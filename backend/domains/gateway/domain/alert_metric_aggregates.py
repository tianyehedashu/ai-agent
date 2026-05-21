"""告警指标聚合快照（纯值对象，由 infrastructure 查询填充）。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AlertMetricAggregates:
    """单条规则在时间窗口内的原始计数，供 domain 评估策略使用。"""

    metric: str
    total_count: int = 0
    error_count: int = 0
    request_count: int = 0
    latency_p95_ms: float | None = None
    cost_sum: float = 0.0
    window_minutes: int = 5


__all__ = ["AlertMetricAggregates"]
