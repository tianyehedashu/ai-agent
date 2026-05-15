"""从虚拟 Key 白名单与路由配置中移除已下线/已删除的虚拟模型名。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from domains.gateway.infrastructure.repositories.model_repository import GatewayRouteRepository
from domains.gateway.infrastructure.repositories.virtual_key_repository import VirtualKeyRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def prune_gateway_model_name_references(
    session: AsyncSession,
    model_names: frozenset[str],
) -> tuple[int, int]:
    """修剪 vkey ``allowed_models`` 与路由 primary/fallback 数组。

    Returns:
        (vkeys_updated, routes_updated)
    """
    if not model_names:
        return 0, 0
    vkeys = VirtualKeyRepository(session)
    routes = GatewayRouteRepository(session)
    vkeys_updated = await vkeys.remove_model_names_from_all_allowed_lists(model_names)
    routes_updated = await routes.remove_model_names_from_all_routes(model_names)
    return vkeys_updated, routes_updated


__all__ = ["prune_gateway_model_name_references"]
