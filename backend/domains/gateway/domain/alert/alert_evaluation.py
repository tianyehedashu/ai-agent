"""Gateway 告警规则评估（纯函数，无 IO）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from .alert_metric_aggregates import AlertMetricAggregates
    from .alert_rule_snapshot import AlertRuleSnapshot


@dataclass(frozen=True, slots=True)
class AlertEvaluationResult:
    """指标已算出且可与阈值比较时的结果。"""

    triggered: bool
    value: float


def alert_cooldown_elapsed(
    last_triggered_at: datetime | None,
    now: datetime,
    *,
    cooldown_seconds: int = 300,
) -> bool:
    """距上次触发是否已超过冷却窗口（无历史则视为可触发）。"""
    if last_triggered_at is None:
        return True
    return (now - last_triggered_at).total_seconds() >= cooldown_seconds


def evaluate_error_rate(
    *,
    threshold: float,
    total_count: int,
    error_count: int,
) -> AlertEvaluationResult | None:
    if total_count == 0:
        return None
    rate = float(error_count) / float(total_count)
    return AlertEvaluationResult(triggered=rate > threshold, value=rate)


def evaluate_request_rate(
    *,
    threshold: float,
    request_count: int,
    window_minutes: int,
) -> AlertEvaluationResult:
    rate_per_min = float(request_count) / max(window_minutes, 1)
    return AlertEvaluationResult(
        triggered=rate_per_min > threshold,
        value=rate_per_min,
    )


def evaluate_latency_p95(*, threshold: float, p95_ms: float | None) -> AlertEvaluationResult:
    p95 = float(p95_ms or 0)
    return AlertEvaluationResult(triggered=p95 > threshold, value=p95)


def evaluate_budget_usage(*, threshold: float, cost_sum: float) -> AlertEvaluationResult:
    total_f = float(cost_sum)
    return AlertEvaluationResult(triggered=total_f > threshold, value=total_f)


def evaluate_alert_rule(
    snapshot: AlertRuleSnapshot,
    aggregates: AlertMetricAggregates,
) -> AlertEvaluationResult | None:
    """按规则快照与聚合数据评估是否触发（metric 分支在 domain）。"""
    threshold = float(snapshot.threshold)
    metric = snapshot.metric
    if metric == "error_rate":
        return evaluate_error_rate(
            threshold=threshold,
            total_count=aggregates.total_count,
            error_count=aggregates.error_count,
        )
    if metric == "request_rate":
        return evaluate_request_rate(
            threshold=threshold,
            request_count=aggregates.request_count,
            window_minutes=aggregates.window_minutes,
        )
    if metric == "latency_p95":
        return evaluate_latency_p95(
            threshold=threshold,
            p95_ms=aggregates.latency_p95_ms,
        )
    if metric == "budget_usage":
        return evaluate_budget_usage(threshold=threshold, cost_sum=aggregates.cost_sum)
    return None


__all__ = [
    "AlertEvaluationResult",
    "alert_cooldown_elapsed",
    "evaluate_alert_rule",
    "evaluate_budget_usage",
    "evaluate_error_rate",
    "evaluate_latency_p95",
    "evaluate_request_rate",
]
