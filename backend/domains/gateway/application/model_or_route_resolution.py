"""按客户端 ``model`` 名解析 ``GatewayModel`` 或 ``GatewayRoute``。

调用入口可以是：

- ``GatewayModel.name``  → 单 deployment（命中），返回原行；
- ``GatewayRoute.virtual_model`` → 多 deployment（命中），返回路由主选 ``GatewayModel``。

返回 ``ResolvedModelName`` 由 ProxyUseCase 校验 capability、附加下游单价、归因日志使用。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from domains.gateway.infrastructure.repositories.model_repository import (
    GatewayModelRepository,
    GatewayRouteRepository,
)

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

    from domains.gateway.infrastructure.models.gateway_model import GatewayModel
    from domains.gateway.infrastructure.models.gateway_route import GatewayRoute
    from domains.gateway.infrastructure.models.system_gateway import (
        SystemGatewayModel,
        SystemGatewayRoute,
    )


@dataclass(frozen=True)
class ResolvedModelName:
    """模型名解析结果。

    Attributes:
        record: 用于 capability / 下游单价基准的 ``GatewayModel`` 行（必有）。
        route: 命中 ``GatewayRoute`` 时存在；表示当前调用走多 deployment 调度。
        via_route: 与 ``route`` 同步；为前端/日志快照预留。
    """

    record: GatewayModel | SystemGatewayModel
    route: GatewayRoute | SystemGatewayRoute | None
    via_route: str | None


async def resolve_model_or_route(
    session: AsyncSession,
    team_id: uuid.UUID,
    name: str,
) -> ResolvedModelName | None:
    """``GatewayModel.name`` 优先，未命中则按 ``GatewayRoute.virtual_model`` 解析主选模型。

    返回 ``None`` 表示该名字既没有对应注册行也没有路由（presentation 层应继续按原 vkey 白名单
    或 LiteLLM 兜底处理）。
    """
    cleaned = name.strip() if name else ""
    if not cleaned:
        return None
    model_repo = GatewayModelRepository(session)
    record = await model_repo.resolve_by_name(team_id, cleaned)
    if record is not None:
        return ResolvedModelName(record=record, route=None, via_route=None)
    route = await GatewayRouteRepository(session).resolve_by_virtual_model(team_id, cleaned)
    if route is None:
        return None
    for primary in route.primary_models or ():
        primary_record = await model_repo.resolve_by_name(team_id, primary)
        if primary_record is not None:
            return ResolvedModelName(
                record=primary_record,
                route=route,
                via_route=route.virtual_model,
            )
    return None


__all__ = ["ResolvedModelName", "resolve_model_or_route"]
