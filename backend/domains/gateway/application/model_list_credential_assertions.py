"""模型列表 ``credential_id`` 筛选与 actor 凭据读权限对齐。"""

from __future__ import annotations

from typing import TYPE_CHECKING
import uuid

from domains.gateway.domain.errors import CredentialNotFoundError
from domains.gateway.domain.team_credential_access import (
    can_filter_team_models_by_credential,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from domains.gateway.application.management.reads import GatewayManagementReadService
    from domains.gateway.infrastructure.models.provider_credential import ProviderCredential
    from domains.gateway.infrastructure.models.system_gateway import SystemProviderCredential


async def _resolve_creator_team_role(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    created_by_user_id: uuid.UUID | None,
) -> str | None:
    if created_by_user_id is None:
        return None
    from domains.tenancy.infrastructure.membership_adapter import TenancyMembershipAdapter
    from libs.iam.tenancy import TenantId

    return await TenancyMembershipAdapter().member_role(
        session,
        tenant_id=TenantId(tenant_id),
        user_id=created_by_user_id,
    )


async def assert_team_credential_filterable_for_model_list(
    session: AsyncSession,
    credential_row: ProviderCredential | SystemProviderCredential,
    credential_id: uuid.UUID,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    is_platform_admin: bool,
) -> None:
    from domains.gateway.infrastructure.models.system_gateway import SystemProviderCredential

    if isinstance(credential_row, SystemProviderCredential):
        return
    creator_role = await _resolve_creator_team_role(
        session,
        tenant_id=tenant_id,
        created_by_user_id=credential_row.created_by_user_id,
    )
    if not can_filter_team_models_by_credential(
        created_by_user_id=credential_row.created_by_user_id,
        actor_user_id=actor_user_id,
        creator_team_role=creator_role,
        is_platform_admin=is_platform_admin,
    ):
        raise CredentialNotFoundError(str(credential_id))


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
    session: AsyncSession,
    reads: GatewayManagementReadService,
    credential_id: uuid.UUID | None,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    is_platform_admin: bool,
) -> None:
    if credential_id is None:
        return
    row = await reads.access.assert_credential_in_team(
        credential_id,
        tenant_id=tenant_id,
        is_platform_admin=is_platform_admin,
    )
    await assert_team_credential_filterable_for_model_list(
        session,
        row,
        credential_id,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        is_platform_admin=is_platform_admin,
    )


async def assert_managed_team_model_list_credential_filter(
    session: AsyncSession,
    credential_id: uuid.UUID | None,
    *,
    allowed_tenant_ids: list[uuid.UUID],
    actor_user_id: uuid.UUID,
    is_platform_admin: bool,
) -> None:
    """跨团队模型列表：凭据须归属协作团队；筛选权限与单团队列表一致（不要求 reveal）。"""
    if credential_id is None:
        return
    from domains.gateway.application.management.reads import GatewayManagementReadService

    reads = GatewayManagementReadService(session)
    row = await reads.access.assert_credential_in_managed_tenants(
        credential_id,
        allowed_tenant_ids=allowed_tenant_ids,
    )
    tenant_id = row.tenant_id
    if tenant_id is None:
        raise CredentialNotFoundError(str(credential_id))
    await assert_team_credential_filterable_for_model_list(
        session,
        row,
        credential_id,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        is_platform_admin=is_platform_admin,
    )


__all__ = [
    "assert_managed_team_model_list_credential_filter",
    "assert_personal_model_list_credential_filter",
    "assert_team_credential_filterable_for_model_list",
    "assert_team_model_list_credential_filter",
]
