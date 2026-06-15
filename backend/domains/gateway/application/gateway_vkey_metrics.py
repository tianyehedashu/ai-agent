"""跨团队 vkey 可观测性指标（进程内计数；非 Prometheus，供 strict 决策与运营观察）。"""

from __future__ import annotations

from collections import defaultdict
import uuid

from utils.logging import get_logger

logger = get_logger(__name__)

AMBIGUOUS_MODEL_INVOCATIONS_TOTAL = "gateway_vkey_ambiguous_model_invocations_total"

_counters: dict[str, int] = defaultdict(int)


def record_ambiguous_model_invocation(*, vkey_id: uuid.UUID, model_name: str) -> None:
    """统计无前缀调用且 model 在 ≥2 个 grant team 存在的次数。"""
    key = f"{AMBIGUOUS_MODEL_INVOCATIONS_TOTAL}|vkey_id={vkey_id}|model={model_name}"
    _counters[key] += 1
    logger.info(
        "vkey ambiguous model invocation vkey_id=%s model=%s count=%d",
        vkey_id,
        model_name,
        _counters[key],
    )


def export_vkey_metrics() -> dict[str, int]:
    """导出当前进程内 vkey 相关计数（测试 / 调试）。"""
    return dict(_counters)


def reset_vkey_metrics_for_tests() -> None:
    """单测隔离用。"""
    _counters.clear()


__all__ = [
    "AMBIGUOUS_MODEL_INVOCATIONS_TOTAL",
    "export_vkey_metrics",
    "record_ambiguous_model_invocation",
    "reset_vkey_metrics_for_tests",
]
