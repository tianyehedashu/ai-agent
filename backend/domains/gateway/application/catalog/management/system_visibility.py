"""系统级可见性 ACL 管理写服务（PlatformAdmin）。"""

from __future__ import annotations

from typing import TYPE_CHECKING
import uuid

from domains.gateway.domain.errors import CredentialNotFoundError, ManagementEntityNotFoundError
from domains.gateway.domain.visibility.gateway_admin import assert_platform_admin
from domains.gateway.domain.visibility.visibility import (
    CredentialVisibility,
    ModelVisibility,
    SubjectKind,
    TargetKind,
    assert_credential_visibility_value,
    assert_model_visibility_value,
    assert_subject_kind,
    assert_target_kind,
)
from domains.gateway.infrastructure.repositories.model_repository import GatewayModelRepository
from domains.gateway.infrastructure.repositories.system_credential_repository import (
    SystemProviderCredentialRepository,
)
from domains.gateway.infrastructure.repositories.system_gateway_grant_repository import (
    SystemGatewayGrantRepository,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from domains.gateway.infrastructure.models.system_gateway import (
        SystemGatewayGrant,
        SystemGatewayModel,
        SystemProviderCredential,
    )


class GatewaySystemVisibilityService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._creds = SystemProviderCredentialRepository(session)
        self._models = GatewayModelRepository(session)
        self._grants = SystemGatewayGrantRepository(session)

    async def set_credential_visibility(
        self,
        credential_id: uuid.UUID,
        *,
        visibility: CredentialVisibility,
        is_platform_admin: bool,
    ) -> SystemProviderCredential:
        assert_platform_admin(is_platform_admin=is_platform_admin)
        assert_credential_visibility_value(visibility)
        row = await self._creds.get(credential_id)
        if row is None:
            raise CredentialNotFoundError(str(credential_id))
        updated = await self._creds.update(credential_id, visibility=visibility)
        assert updated is not None
        return updated

    async def set_model_visibility(
        self,
        model_id: uuid.UUID,
        *,
        visibility: ModelVisibility,
        is_platform_admin: bool,
    ) -> SystemGatewayModel:
        assert_platform_admin(is_platform_admin=is_platform_admin)
        assert_model_visibility_value(visibility)
        row = await self._models.get_system(model_id)
        if row is None:
            raise ManagementEntityNotFoundError("system_model", str(model_id))
        updated = await self._models.update_system(model_id, visibility=visibility)
        assert updated is not None
        return updated

    async def list_grants_for_subject(
        self,
        subject_kind: SubjectKind | str,
        subject_id: uuid.UUID,
        *,
        is_platform_admin: bool,
    ) -> list[SystemGatewayGrant]:
        assert_platform_admin(is_platform_admin=is_platform_admin)
        kind = assert_subject_kind(str(subject_kind))
        return await self._grants.list_for_subject(kind, subject_id)

    async def create_grant(
        self,
        *,
        subject_kind: SubjectKind | str,
        subject_id: uuid.UUID,
        target_kind: TargetKind | str,
        target_id: uuid.UUID,
        granted_by: uuid.UUID,
        note: str | None,
        is_platform_admin: bool,
    ) -> SystemGatewayGrant:
        assert_platform_admin(is_platform_admin=is_platform_admin)
        sk = assert_subject_kind(str(subject_kind))
        tk = assert_target_kind(str(target_kind))
        if sk == "credential":
            if await self._creds.get(subject_id) is None:
                raise CredentialNotFoundError(str(subject_id))
        elif await self._models.get_system(subject_id) is None:
            raise ManagementEntityNotFoundError("system_model", str(subject_id))
        row = await self._grants.create(
            subject_kind=sk,
            subject_id=subject_id,
            target_kind=tk,
            target_id=target_id,
            granted_by=granted_by,
            note=note,
        )
        await self._invalidate_grants_cache_for_target(tk, target_id)
        return row

    async def update_grant(
        self,
        grant_id: uuid.UUID,
        *,
        enabled: bool | None,
        note: str | None,
        is_platform_admin: bool,
    ) -> SystemGatewayGrant:
        assert_platform_admin(is_platform_admin=is_platform_admin)
        row = await self._grants.update(grant_id, enabled=enabled, note=note)
        if row is None:
            raise ManagementEntityNotFoundError("system_grant", str(grant_id))
        await self._invalidate_grants_cache_for_target(row.target_kind, row.target_id)
        return row

    async def delete_grant(
        self,
        grant_id: uuid.UUID,
        *,
        is_platform_admin: bool,
    ) -> None:
        assert_platform_admin(is_platform_admin=is_platform_admin)
        existing = await self._grants.get(grant_id)
        if existing is None:
            raise ManagementEntityNotFoundError("system_grant", str(grant_id))
        if not await self._grants.delete(grant_id):
            raise ManagementEntityNotFoundError("system_grant", str(grant_id))
        await self._invalidate_grants_cache_for_target(existing.target_kind, existing.target_id)

    async def _invalidate_grants_cache_for_target(
        self,
        target_kind: str,
        target_id: uuid.UUID,
    ) -> None:
        from domains.gateway.application.observability.gateway_cache_invalidation import (
            invalidate_gateway_grants_cache_for_team,
        )

        if target_kind == "team":
            await invalidate_gateway_grants_cache_for_team(target_id)
        else:
            from domains.gateway.application.grant.system_grants_cache import (
                invalidate_all_grants_cache,
            )

            await invalidate_all_grants_cache()

    async def list_grants_for_target(
        self,
        target_kind: TargetKind | str,
        target_id: uuid.UUID,
        *,
        is_platform_admin: bool,
    ) -> list[SystemGatewayGrant]:
        assert_platform_admin(is_platform_admin=is_platform_admin)
        tk = assert_target_kind(str(target_kind))
        return await self._grants.list_for_target(tk, target_id)


__all__ = [
    "CredentialVisibility",
    "GatewaySystemVisibilityService",
    "ModelVisibility",
]
