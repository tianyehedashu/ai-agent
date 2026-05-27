"""按客户端 ``model`` 名解析 ``GatewayModel`` 或 ``GatewayRoute``。

调用入口可以是：

- ``GatewayModel.name``  → 单 deployment（命中），返回原行；
- ``GatewayRoute.virtual_model`` → 多 deployment（命中），返回路由主选 ``GatewayModel``。

返回 ``ResolvedModelName`` 由 ProxyUseCase 校验 capability、附加下游单价、归因日志使用。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from domains.gateway.application.gateway_model_listing import resolve_by_name_visible
from domains.gateway.infrastructure.repositories.gateway_route_repository import (
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


async def _resolve_personal_team_model(
    session: AsyncSession,
    current_team_id: uuid.UUID,
    name: str,
    *,
    user_id: uuid.UUID,
) -> GatewayModel | SystemGatewayModel | None:
    """共享团队 vkey 下调用个人团队 ``gateway_models`` 注册别名。"""
    from domains.tenancy.application.team_service import TeamService

    personal = await TeamService(session).ensure_personal_team(user_id)
    if personal.id == current_team_id:
        return None
    return await resolve_by_name_visible(
        session, personal.id, name, user_id=user_id
    )


async def _resolve_model_or_route_uncached(
    session: AsyncSession,
    team_id: uuid.UUID,
    name: str,
    *,
    user_id: uuid.UUID | None = None,
) -> ResolvedModelName | None:
    cleaned = name.strip() if name else ""
    if not cleaned:
        return None

    if user_id is not None:
        personal_record = await _resolve_personal_team_model(
            session, team_id, cleaned, user_id=user_id
        )
        if personal_record is not None:
            return ResolvedModelName(
                record=personal_record,
                route=None,
                via_route=None,
            )

    record = await resolve_by_name_visible(
        session, team_id, cleaned, user_id=user_id
    )
    if record is not None:
        return ResolvedModelName(record=record, route=None, via_route=None)
    route = await GatewayRouteRepository(session).resolve_by_virtual_model(team_id, cleaned)
    if route is None:
        return None
    for primary in route.primary_models or ():
        primary_record = await resolve_by_name_visible(
            session, team_id, primary, user_id=user_id
        )
        if primary_record is not None:
            return ResolvedModelName(
                record=primary_record,
                route=route,
                via_route=route.virtual_model,
            )
    return None


async def resolve_model_or_route(
    session: AsyncSession,
    team_id: uuid.UUID,
    name: str,
    *,
    user_id: uuid.UUID | None = None,
) -> ResolvedModelName | None:
    """``GatewayModel.name`` 优先，未命中则按 ``GatewayRoute.virtual_model`` 解析主选模型。

    返回 ``None`` 表示该名字既没有对应注册行也没有路由（presentation 层应继续按原 vkey 白名单
    或 LiteLLM 兜底处理）。
    """
    cleaned = name.strip() if name else ""
    if not cleaned:
        return None

    from bootstrap.config import settings
    from domains.gateway.application.resolve_model_cache import (
        CACHE_MISS,
        hydrate_resolve_cache_entry,
        is_negative_resolve_cache,
        peek_resolve_cache_entry,
        put_resolve_cache_entry,
    )

    if settings.gateway_resolve_model_cache_enabled:
        cached = peek_resolve_cache_entry(team_id, cleaned, user_id=user_id)
        if cached is not CACHE_MISS:
            if is_negative_resolve_cache(cached):
                return None
            return await hydrate_resolve_cache_entry(session, cached)

    resolved = await _resolve_model_or_route_uncached(
        session, team_id, cleaned, user_id=user_id
    )
    if settings.gateway_resolve_model_cache_enabled:
        put_resolve_cache_entry(team_id, cleaned, user_id=user_id, resolved=resolved)
    return resolved


__all__ = ["ResolvedModelName", "resolve_model_or_route"]
