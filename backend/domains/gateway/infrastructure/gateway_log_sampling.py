"""网关请求明细写入策略（采样），供 CustomLogger 与单测复用。"""

from __future__ import annotations

import hashlib


def deterministic_success_sample(*, request_key: str, sample_rate: float) -> bool:
    """按 request_key 稳定哈希决定是否采样命中（成功请求写明细）。"""
    if sample_rate >= 1.0:
        return True
    if sample_rate <= 0.0:
        return False
    digest = hashlib.sha256(request_key.encode("utf-8", errors="replace")).digest()
    val = int.from_bytes(digest[:4], "big") % 10_000
    return val < int(sample_rate * 10_000)


def should_persist_request_log_row(
    *,
    status: str,
    cost_usd: float,
    request_id: str | None,
    litellm_call_id: str | None,
    success_sample_rate: float,
    always_persist_non_success: bool,
    always_persist_cost_above_usd: float | None,
    force_persist: bool = False,
) -> bool:
    """是否写入 ``gateway_request_logs`` 行（Redis 计数仍可单独更新）。"""
    if force_persist:
        return True
    if status != "success":
        return always_persist_non_success
    if always_persist_cost_above_usd is not None and cost_usd >= float(
        always_persist_cost_above_usd
    ):
        return True
    key = (request_id or litellm_call_id or "").strip() or "__empty__"
    return deterministic_success_sample(request_key=key, sample_rate=success_sample_rate)


__all__ = [
    "deterministic_success_sample",
    "should_persist_request_log_row",
]
