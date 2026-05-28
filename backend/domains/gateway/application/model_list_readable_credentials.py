"""模型列表 q 凭据名搜索与 actor 可见凭据 id 解析。"""

from __future__ import annotations

from typing import TYPE_CHECKING
import uuid

from domains.gateway.domain.team_credential_access import (
    filter_team_credentials_visible_to_actor,
)
from domains.gateway.infrastructure.repositories.credential_repository import (
    ProviderCredentialRepository,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def readable_user_credential_ids(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> frozenset[uuid.UUID]:
    rows = await ProviderCredentialRepository(session).list_for_user(user_id)
    return frozenset(row.id for row in rows)


async def readable_team_credential_ids_for_tenant(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    actor_user_id: uuid.UUID,
    team_role: str,
    is_platform_admin: bool,
) -> frozenset[uuid.UUID]:
    rows = await ProviderCredentialRepository(session).list_for_tenant(tenant_id)
    visible = filter_team_credentials_visible_to_actor(
        rows,
        actor_user_id=actor_user_id,
        team_role=team_role,
        is_platform_admin=is_platform_admin,
    )
    return frozenset(row.id for row in visible)


async def readable_team_credential_ids_for_tenants(
    session: AsyncSession,
    tenant_ids: list[uuid.UUID],
    *,
    actor_user_id: uuid.UUID,
    role_by_tenant: dict[uuid.UUID, str],
    is_platform_admin: bool,
) -> frozenset[uuid.UUID]:
    if not tenant_ids:
        return frozenset()
    repo = ProviderCredentialRepository(session)
    out: set[uuid.UUID] = set()
    for tenant_id in tenant_ids:
        rows = await repo.list_for_tenant(tenant_id)
        team_role = role_by_tenant.get(tenant_id, "member")
        visible = filter_team_credentials_visible_to_actor(
            rows,
            actor_user_id=actor_user_id,
            team_role=team_role,
            is_platform_admin=is_platform_admin,
        )
        out.update(row.id for row in visible)
    return frozenset(out)


__all__ = [
    "readable_team_credential_ids_for_tenant",
    "readable_team_credential_ids_for_tenants",
    "readable_user_credential_ids",
]
