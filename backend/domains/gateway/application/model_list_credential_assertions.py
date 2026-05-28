"""模型列表 ``credential_id`` 筛选与 actor 凭据读权限对齐。"""

from __future__ import annotations

from typing import TYPE_CHECKING
import uuid

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
    allowed_tenant_ids: list[uuid.UUID],
) -> None:
    """跨团队模型列表：凭据须归属协作团队，不要求 reveal。"""
    if credential_id is None:
        return
    from domains.gateway.application.management.reads import GatewayManagementReadService

    reads = GatewayManagementReadService(session)
    await reads.assert_credential_in_managed_tenants(
        credential_id,
        allowed_tenant_ids=allowed_tenant_ids,
    )


__all__ = [
    "assert_managed_team_model_list_credential_filter",
    "assert_personal_model_list_credential_filter",
    "assert_team_model_list_credential_filter",
]
