"""虚拟路由请求日志快照（纯函数，与 ``gateway_route_snapshot`` 元数据对齐）。"""

from __future__ import annotations

from typing import Any, Protocol


class _RouteSnapshotSource(Protocol):
    virtual_model: str
    primary_models: list[str] | None
    fallbacks_general: list[str] | None
    fallbacks_content_policy: list[str] | None
    fallbacks_context_window: list[str] | None
    strategy: str | None
    retry_policy: dict[str, Any] | None


def build_route_snapshot_metadata(route: _RouteSnapshotSource) -> dict[str, Any]:
    """构造写入 ``gateway_request_logs.route_snapshot`` 的快照 dict。"""
    retry = route.retry_policy
    return {
        "virtual_model": route.virtual_model,
        "primary_models": list(route.primary_models or []),
        "fallbacks_general": list(route.fallbacks_general or []),
        "fallbacks_content_policy": list(route.fallbacks_content_policy or []),
        "fallbacks_context_window": list(route.fallbacks_context_window or []),
        "strategy": route.strategy,
        "retry_policy": dict(retry) if isinstance(retry, dict) and retry else None,
    }


__all__ = ["build_route_snapshot_metadata"]
