"""路由跨团队共享授权的生命周期撤销（成员移除 / 团队删除 / 离线清理）。

与 ``virtual_key_team_grant_writes`` 的 ``revoke_grants_for_*`` 对称；不触发 Router
reload（代理热路径以委派解析为权威闸门，stale deployment 不构成越权），但须失效
``resolve_model_or_route`` 进程内缓存以免撤销后 TTL 内仍可调用。
"""

from __future__ import annotations

from typing import TYPE_CHECKING
import uuid

from domains.gateway.application.observability.gateway_cache_invalidation import (
    invalidate_gateway_read_caches_for_tenant,
)
from domains.gateway.infrastructure.repositories.gateway_route_grant_repository import (
    GatewayRouteTeamGrantRepository,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def revoke_route_grants_for_user_team_membership(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    reason: str = "membership_lost",
) -> int:
    """``remove_member`` 同步触发：撤销该用户共享进该 team 的全部路由 grant。"""
    repo = GatewayRouteTeamGrantRepository(session)
    count = await repo.revoke_grants_for_user_team(
        user_id=user_id,
        tenant_id=tenant_id,
        reason=reason,
    )
    if count > 0:
        invalidate_gateway_read_caches_for_tenant(tenant_id)
    return count


async def revoke_route_grants_for_team_deleted(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    reason: str = "team_archived",
) -> int:
    """``delete_shared_team`` 同步触发：撤销指向该 team 的全部路由 grant。"""
    repo = GatewayRouteTeamGrantRepository(session)
    count = await repo.revoke_all_for_tenant(tenant_id, reason=reason)
    if count > 0:
        invalidate_gateway_read_caches_for_tenant(tenant_id)
    return count


__all__ = [
    "revoke_route_grants_for_team_deleted",
    "revoke_route_grants_for_user_team_membership",
]
