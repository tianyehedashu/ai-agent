"""个人资源 grant 写侧权限与归属校验。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from libs.exceptions import NotFoundError, PermissionDeniedError, ValidationError

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

    from domains.gateway.infrastructure.models.gateway_model import GatewayModel
    from domains.gateway.infrastructure.models.provider_credential import ProviderCredential


async def assert_actor_member_of_team(
    session: AsyncSession,
    *,
    actor_user_id: uuid.UUID,
    team_id: uuid.UUID,
    is_platform_admin: bool = False,
) -> None:
    if is_platform_admin:
        return
    from domains.tenancy.application.team_service import TeamService

    memberships = await TeamService(session).list_gateway_team_memberships(
        actor_user_id,
        is_platform_admin=False,
    )
    if not any(m.team_id == team_id for m in memberships):
        raise PermissionDeniedError("无权向该团队授权资源")


def assert_user_owns_byok_credential(
    cred: ProviderCredential,
    *,
    actor_user_id: uuid.UUID,
    is_platform_admin: bool = False,
) -> None:
    if is_platform_admin:
        return
    if cred.scope != "user" or cred.scope_id != actor_user_id:
        raise PermissionDeniedError("仅可授权本人 BYOK 凭据")


async def load_owner_byok_credential(
    session: AsyncSession,
    credential_id: uuid.UUID,
    *,
    actor_user_id: uuid.UUID,
    is_platform_admin: bool = False,
) -> ProviderCredential:
    from domains.gateway.infrastructure.repositories.credential_repository import (
        ProviderCredentialRepository,
    )

    cred = await ProviderCredentialRepository(session).get(credential_id)
    if cred is None:
        raise NotFoundError(f"Credential {credential_id} not found")
    assert_user_owns_byok_credential(
        cred,
        actor_user_id=actor_user_id,
        is_platform_admin=is_platform_admin,
    )
    return cred


async def load_owner_personal_model(
    session: AsyncSession,
    model_id: uuid.UUID,
    *,
    actor_user_id: uuid.UUID,
    is_platform_admin: bool = False,
) -> GatewayModel:
    from domains.gateway.infrastructure.repositories.model_repository import GatewayModelRepository
    from domains.tenancy.application.team_service import TeamService

    model = await GatewayModelRepository(session).get(model_id)
    if model is None or model.tenant_id is None:
        raise NotFoundError(f"Model {model_id} not found")
    personal = await TeamService(session).ensure_personal_team(actor_user_id)
    if not is_platform_admin and model.tenant_id != personal.id:
        raise PermissionDeniedError("仅可授权本人个人模型")
    cred = await load_owner_byok_credential(
        session,
        model.credential_id,
        actor_user_id=actor_user_id,
        is_platform_admin=is_platform_admin,
    )
    if cred.scope_id != actor_user_id and not is_platform_admin:
        raise ValidationError("个人模型须绑定本人 BYOK 凭据")
    return model


__all__ = [
    "assert_actor_member_of_team",
    "assert_user_owns_byok_credential",
    "load_owner_byok_credential",
    "load_owner_personal_model",
]
