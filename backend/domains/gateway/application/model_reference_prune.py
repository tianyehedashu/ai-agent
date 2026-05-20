"""从虚拟 Key 白名单与路由配置中移除或重命名已下线/已改名的虚拟模型名。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from domains.gateway.infrastructure.repositories.model_repository import GatewayRouteRepository
from domains.gateway.infrastructure.repositories.virtual_key_repository import VirtualKeyRepository

if TYPE_CHECKING:
    import uuid

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


async def rename_gateway_model_name_references(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID | None,
    old_name: str,
    new_name: str,
) -> tuple[int, int]:
    """按租户作用域将 vkey 白名单与路由中的虚拟模型名 old_name 替换为 new_name。

    ``tenant_id`` 为 ``None`` 时仅更新系统级路由，不修改各租户 vkey。

    Returns:
        (vkeys_updated, routes_updated)
    """
    if old_name == new_name:
        return 0, 0
    vkeys = VirtualKeyRepository(session)
    routes = GatewayRouteRepository(session)
    if tenant_id is None:
        vkeys_updated = 0
        routes_updated = await routes.rename_model_name_in_global_routes(old_name, new_name)
    else:
        vkeys_updated = await vkeys.rename_model_name_in_tenant_allowed_lists(
            tenant_id, old_name, new_name
        )
        routes_updated = await routes.rename_model_name_in_tenant_routes(
            tenant_id, old_name, new_name
        )
    return vkeys_updated, routes_updated


__all__ = ["prune_gateway_model_name_references", "rename_gateway_model_name_references"]
