"""virtual_key_team_grant_writes — 跨团队授权写服务"""

from __future__ import annotations

from typing import TYPE_CHECKING
import uuid

from domains.gateway.infrastructure.repositories.virtual_key_team_grant_repository import (
    VirtualKeyTeamGrantRepository,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

    from domains.gateway.infrastructure.models.virtual_key_team_grant import (
        GatewayVirtualKeyTeamGrant,
    )


async def ensure_self_grant_for_vkey(
    session: AsyncSession,
    *,
    vkey_id: uuid.UUID,
    tenant_id: uuid.UUID,
    granted_by_user_id: uuid.UUID,
) -> GatewayVirtualKeyTeamGrant:
    """幂等写入 vkey 主属 team 自洽 grant（创建 vkey 时调用）。"""
    repo = VirtualKeyTeamGrantRepository(session)
    return await repo.upsert_active(
        vkey_id=vkey_id,
        tenant_id=tenant_id,
        granted_by_user_id=granted_by_user_id,
        is_self=True,
    )


async def grant_vkey_to_teams(
    session: AsyncSession,
    *,
    vkey_id: uuid.UUID,
    vkey_tenant_id: uuid.UUID,
    tenant_ids: Sequence[uuid.UUID],
    granted_by_user_id: uuid.UUID,
) -> list[GatewayVirtualKeyTeamGrant]:
    """幂等批量授权 vkey 到指定 team。

    主属 team（tenant_id == vkey.tenant_id）会被跳过（由自洽 grant 覆盖）。
    """
    repo = VirtualKeyTeamGrantRepository(session)
    results: list[GatewayVirtualKeyTeamGrant] = []
    for tenant_id in tenant_ids:
        if tenant_id == vkey_tenant_id:
            continue
        grant = await repo.upsert_active(
            vkey_id=vkey_id,
            tenant_id=tenant_id,
            granted_by_user_id=granted_by_user_id,
            is_self=False,
        )
        results.append(grant)
    return results


async def revoke_vkey_team_grant(
    session: AsyncSession,
    *,
    vkey_id: uuid.UUID,
    tenant_id: uuid.UUID,
    reason: str = "owner_revoked",
) -> bool:
    """撤销一行 active grant；is_self=TRUE 应被前置校验拦截。"""
    repo = VirtualKeyTeamGrantRepository(session)
    return await repo.revoke(vkey_id, tenant_id, reason=reason)


async def revoke_grants_for_user_team_membership(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    reason: str = "membership_lost",
) -> int:
    """``remove_member`` 同步触发：撤销用户在某 team 上的非自洽 grant。"""
    repo = VirtualKeyTeamGrantRepository(session)
    return await repo.revoke_grants_for_user_team(
        user_id=user_id,
        tenant_id=tenant_id,
        reason=reason,
    )


async def revoke_grants_for_team_deleted(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
) -> int:
    """``delete_shared_team`` 同步触发：撤销所有指向该 team 的 grant。"""
    repo = VirtualKeyTeamGrantRepository(session)
    return await repo.revoke_all_for_tenant(tenant_id, reason="team_archived")


__all__ = [
    "ensure_self_grant_for_vkey",
    "grant_vkey_to_teams",
    "revoke_grants_for_team_deleted",
    "revoke_grants_for_user_team_membership",
    "revoke_vkey_team_grant",
]
