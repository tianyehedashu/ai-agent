"""模型列表 ``credential_id`` 筛选与 actor 凭据读权限对齐。"""

from __future__ import annotations

from typing import TYPE_CHECKING
import uuid

from domains.gateway.domain.errors import CredentialNotFoundError
from domains.gateway.domain.team_credential_access import (
    filter_team_credentials_visible_to_actor,
)
from domains.gateway.infrastructure.repositories.credential_repository import (
    ProviderCredentialRepository,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from domains.gateway.application.management.reads import GatewayManagementReadService


async def assert_personal_model_list_credential_filter(
    reads: GatewayManagementReadService,
    credential_id: uuid.UUID | None,
    *,
    user_id: uuid.UUID,
) -> None:
    if credential_id is None:
        return
    await reads.get_user_credential_for_owner(credential_id, user_id)


async def assert_team_model_list_credential_filter(
    reads: GatewayManagementReadService,
    credential_id: uuid.UUID | None,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    team_role: str,
    is_platform_admin: bool,
) -> None:
    if credential_id is None:
        return
    await reads.get_managed_credential_for_team(
        credential_id,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        team_role=team_role,
        is_platform_admin=is_platform_admin,
    )


async def assert_managed_team_model_list_credential_filter(
    session: AsyncSession,
    credential_id: uuid.UUID | None,
    *,
    user_id: uuid.UUID,
    allowed_tenant_ids: list[uuid.UUID],
    role_by_tenant: dict[uuid.UUID, str],
) -> None:
    if credential_id is None:
        return
    row = await ProviderCredentialRepository(session).get(credential_id)
    if row is None or row.tenant_id is None:
        raise CredentialNotFoundError(str(credential_id))
    allowed = set(allowed_tenant_ids)
    if row.tenant_id not in allowed:
        raise CredentialNotFoundError(str(credential_id))
    team_role = role_by_tenant.get(row.tenant_id, "member")
    visible = filter_team_credentials_visible_to_actor(
        [row],
        actor_user_id=user_id,
        team_role=team_role,
        is_platform_admin=False,
    )
    if not visible:
        raise CredentialNotFoundError(str(credential_id))


__all__ = [
    "assert_managed_team_model_list_credential_filter",
    "assert_personal_model_list_credential_filter",
    "assert_team_model_list_credential_filter",
]
