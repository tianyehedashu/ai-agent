"""个人资源 grant 写侧。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from domains.gateway.application.observability.gateway_cache_invalidation import (
    invalidate_gateway_read_caches_for_tenant_with_grants,
    invalidate_gateway_resource_grants_cache_for_team,
)
from domains.gateway.infrastructure.repositories.resource_grant_repository import (
    GatewayResourceGrantRepository,
)

from .resource_grant_policy import (
    assert_actor_member_of_team,
    load_owner_byok_credential,
    load_owner_personal_model,
)

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

    from domains.gateway.infrastructure.models.resource_grant import GatewayResourceGrant


class ResourceGrantWriteService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = GatewayResourceGrantRepository(session)

    async def grant_credential_to_teams(
        self,
        *,
        credential_id: uuid.UUID,
        target_team_ids: list[uuid.UUID],
        actor_user_id: uuid.UUID,
        is_platform_admin: bool = False,
        note: str | None = None,
    ) -> list[GatewayResourceGrant]:
        cred = await load_owner_byok_credential(
            self._session,
            credential_id,
            actor_user_id=actor_user_id,
            is_platform_admin=is_platform_admin,
        )
        owner_id = cred.scope_id
        if owner_id is None:
            raise ValueError("BYOK credential missing scope_id")
        created: list[GatewayResourceGrant] = []
        for team_id in target_team_ids:
            await assert_actor_member_of_team(
                self._session,
                actor_user_id=actor_user_id,
                team_id=team_id,
                is_platform_admin=is_platform_admin,
            )
            row = await self._repo.create(
                owner_user_id=owner_id,
                subject_kind="credential",
                subject_id=credential_id,
                target_team_id=team_id,
                granted_by=actor_user_id,
                note=note,
            )
            created.append(row)
            await self._invalidate_team(team_id)
        return created

    async def grant_model_to_teams(
        self,
        *,
        model_id: uuid.UUID,
        target_team_ids: list[uuid.UUID],
        actor_user_id: uuid.UUID,
        is_platform_admin: bool = False,
        note: str | None = None,
    ) -> list[GatewayResourceGrant]:
        model = await load_owner_personal_model(
            self._session,
            model_id,
            actor_user_id=actor_user_id,
            is_platform_admin=is_platform_admin,
        )
        from domains.tenancy.application.team_service import TeamService

        personal = await TeamService(self._session).ensure_personal_team(actor_user_id)
        owner_id = actor_user_id
        created: list[GatewayResourceGrant] = []
        for team_id in target_team_ids:
            await assert_actor_member_of_team(
                self._session,
                actor_user_id=actor_user_id,
                team_id=team_id,
                is_platform_admin=is_platform_admin,
            )
            row = await self._repo.create(
                owner_user_id=owner_id,
                subject_kind="model",
                subject_id=model.id,
                target_team_id=team_id,
                granted_by=actor_user_id,
                note=note,
            )
            created.append(row)
            await self._invalidate_team(team_id)
        _ = personal
        return created

    async def update_grant(
        self,
        grant_id: uuid.UUID,
        *,
        actor_user_id: uuid.UUID,
        enabled: bool | None = None,
        note: str | None = None,
        is_platform_admin: bool = False,
    ) -> GatewayResourceGrant:
        row = await self._repo.get(grant_id)
        if row is None:
            raise ValueError(f"Grant {grant_id} not found")
        if not is_platform_admin and row.owner_user_id != actor_user_id:
            from libs.exceptions import PermissionDeniedError

            raise PermissionDeniedError("仅资源 owner 可修改授权")
        updated = await self._repo.update(grant_id, enabled=enabled, note=note)
        assert updated is not None
        await self._invalidate_team(updated.target_team_id)
        return updated

    async def revoke_grant(
        self,
        grant_id: uuid.UUID,
        *,
        actor_user_id: uuid.UUID,
        is_platform_admin: bool = False,
    ) -> None:
        row = await self._repo.get(grant_id)
        if row is None:
            return
        if not is_platform_admin and row.owner_user_id != actor_user_id:
            from libs.exceptions import PermissionDeniedError

            raise PermissionDeniedError("仅资源 owner 可撤销授权")
        target = row.target_team_id
        await self._repo.delete(grant_id)
        await self._invalidate_team(target)

    async def _invalidate_team(self, team_id: uuid.UUID) -> None:
        invalidate_gateway_read_caches_for_tenant_with_grants(team_id)
        await invalidate_gateway_resource_grants_cache_for_team(team_id)


__all__ = ["ResourceGrantWriteService"]
