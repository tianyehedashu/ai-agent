"""vkey 跨团队 grant 目标校验（application 层）。"""

from __future__ import annotations

from typing import TYPE_CHECKING
import uuid

from domains.gateway.domain.errors import VkeyGrantTargetNotMemberError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession


async def _actor_membership_ids(session: AsyncSession, actor_user_id: uuid.UUID) -> set[uuid.UUID]:
    from domains.tenancy.application.team_membership_queries import list_team_ids_for_user

    return set(await list_team_ids_for_user(session, actor_user_id))


async def assert_actor_member_of_vkey_grant_targets(
    session: AsyncSession,
    *,
    actor_user_id: uuid.UUID,
    tenant_ids: Sequence[uuid.UUID],
) -> None:
    """Grant API：请求中的每个 tenant 均须在 actor membership 内。"""
    if not tenant_ids:
        return
    membership = await _actor_membership_ids(session, actor_user_id)
    invalid = [tid for tid in tenant_ids if tid not in membership]
    if invalid:
        raise VkeyGrantTargetNotMemberError(invalid)


async def resolve_extra_vkey_grant_tenant_ids(
    session: AsyncSession,
    *,
    actor_user_id: uuid.UUID,
    bound_team_id: uuid.UUID,
    requested_tenant_ids: Sequence[uuid.UUID],
) -> list[uuid.UUID]:
    """创建 vkey 时解析额外 grant 目标：跳过主属 team，去重，校验 membership。"""
    if not requested_tenant_ids:
        return []
    membership = await _actor_membership_ids(session, actor_user_id)
    extra: list[uuid.UUID] = []
    invalid: list[uuid.UUID] = []
    seen: set[uuid.UUID] = set()
    for tenant_id in requested_tenant_ids:
        if tenant_id == bound_team_id or tenant_id in seen:
            continue
        seen.add(tenant_id)
        if tenant_id not in membership:
            invalid.append(tenant_id)
        else:
            extra.append(tenant_id)
    if invalid:
        raise VkeyGrantTargetNotMemberError(invalid)
    return extra


__all__ = [
    "assert_actor_member_of_vkey_grant_targets",
    "resolve_extra_vkey_grant_tenant_ids",
]
