"""可绑定凭据解析：application 层 IO 编排（team-scope/grant → platform_admin fallback system）。

权限规则（``is_platform_admin`` fallback system 凭据、跨团队个人 grant）在此编排，
不泄漏到 infrastructure 仓储。与 ``resource_grant_filter`` 同层（application IO 编排），
供 management reads/writes/access_assertions 共用。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from domains.gateway.application.grant.resource_grant_filter import (
    is_credential_granted_to_team,
)
from domains.gateway.domain.errors import CredentialNotFoundError
from domains.gateway.infrastructure.repositories.credential_repository import (
    ProviderCredentialRepository,
)
from domains.gateway.infrastructure.repositories.system_credential_repository import (
    SystemProviderCredentialRepository,
)

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

    from domains.gateway.infrastructure.models.provider_credential import ProviderCredential
    from domains.gateway.infrastructure.models.system_gateway import (
        SystemProviderCredential,
    )


async def resolve_bindable_credential(
    session: AsyncSession,
    *,
    credential_id: uuid.UUID,
    tenant_id: uuid.UUID,
    is_platform_admin: bool,
) -> ProviderCredential | SystemProviderCredential | None:
    """解析可绑定到团队网关模型的凭据。

    查询顺序：
    1. team-scope 凭据（tenant 匹配）
    2. 跨团队个人 grant 凭据（scope=user 且已授权给该团队）
    3. system 凭据 —— 仅 platform_admin 可绑定（fallback）

    仓储只做单表 tenant 匹配；``is_platform_admin`` 权限语义与 grant 编排在本层收口。
    """
    row = await ProviderCredentialRepository(session).get(credential_id)
    if row is not None:
        if row.tenant_id == tenant_id:
            return row
        if row.scope == "user" and row.scope_id is not None:
            if await is_credential_granted_to_team(
                session,
                credential_id=credential_id,
                target_team_id=tenant_id,
            ):
                return row

    if is_platform_admin:
        return await SystemProviderCredentialRepository(session).get(credential_id)
    return None


async def assert_bindable_credential(
    session: AsyncSession,
    *,
    credential_id: uuid.UUID,
    tenant_id: uuid.UUID,
    is_platform_admin: bool,
) -> ProviderCredential | SystemProviderCredential:
    """``resolve_bindable_credential`` 的断言变体：解析失败抛 ``CredentialNotFoundError``。"""
    row = await resolve_bindable_credential(
        session,
        credential_id=credential_id,
        tenant_id=tenant_id,
        is_platform_admin=is_platform_admin,
    )
    if row is None:
        raise CredentialNotFoundError(str(credential_id))
    return row


__all__ = ["assert_bindable_credential", "resolve_bindable_credential"]
