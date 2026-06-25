"""虚拟路由请求日志快照（纯函数，与 ``gateway_route_snapshot`` 元数据对齐）。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from uuid import UUID


class _RouteSnapshotSource(Protocol):
    # 只读 property 成员（协变）：让 ORM 的 ``list[str]`` 列与 ``list[str] | None`` 兼容，
    # 避免可变属性协议的不变性导致 ``GatewayRoute`` / 快照类无法结构匹配。
    @property
    def virtual_model(self) -> str: ...
    @property
    def primary_models(self) -> list[str] | None: ...
    @property
    def fallbacks_general(self) -> list[str] | None: ...
    @property
    def fallbacks_content_policy(self) -> list[str] | None: ...
    @property
    def fallbacks_context_window(self) -> list[str] | None: ...
    @property
    def strategy(self) -> str | None: ...
    @property
    def retry_policy(self) -> dict[str, Any] | None: ...


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


def build_delegated_route_snapshot_metadata(
    route: _RouteSnapshotSource,
    *,
    exposed_alias: str | None,
    owner_tenant_id: UUID | None,
    owner_user_id: UUID | None,
    route_grant_id: UUID | None,
) -> dict[str, Any]:
    """委派（跨团队共享）路由快照：基础快照 + 暴露别名、owner 归因与 grant 关联键。

    与 ``route_snapshot_cache.get_route_snapshot_metadata`` 不复用键空间——后者按
    ``(consumer_team_id, virtual_model)`` 查本地路由，委派场景下消费团队**无**同名本地路由，
    查必落空；此处直接以已解析的 owner 路由构建，零额外查库且单一真源（快照构形仍在 domain）。
    """
    snap = build_route_snapshot_metadata(route)
    snap["delegated"] = True
    snap["route_grant_id"] = str(route_grant_id) if route_grant_id is not None else None
    snap["exposed_alias"] = exposed_alias
    snap["owner_tenant_id"] = str(owner_tenant_id) if owner_tenant_id is not None else None
    snap["owner_user_id"] = str(owner_user_id) if owner_user_id is not None else None
    return snap


__all__ = [
    "build_delegated_route_snapshot_metadata",
    "build_route_snapshot_metadata",
]
