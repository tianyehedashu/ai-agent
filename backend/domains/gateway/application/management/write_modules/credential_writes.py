"""Gateway 管理面变更应用服务（写侧分包；对外 API 不变）。"""

from __future__ import annotations

from datetime import datetime
from typing import Any
import uuid

from bootstrap.config import settings
from domains.gateway.application.management.credential_read_mappers import (
    ensure_credential_read_model,
)
from domains.gateway.application.management.credential_read_model import CredentialReadModel
from domains.gateway.domain.credential_persist import normalize_credential_write_fields
from domains.gateway.domain.errors import (
    CredentialNameConflictError,
    CredentialNotFoundError,
    SystemVirtualKeyRevokeForbiddenError,
    TeamPermissionDeniedError,
    VirtualKeyNotFoundError,
)
from domains.gateway.domain.guardrail_policy import assert_vkey_guardrail_create_allowed
from domains.gateway.domain.types import (
    VirtualKeyBatchRevokeReason,
    is_config_managed_system_credential,
)
from domains.gateway.domain.virtual_key_access import assert_virtual_key_accessible_by_actor
from libs.exceptions import ValidationError
from utils.logging import get_logger

logger = get_logger(__name__)


def _credential_update_api_fields(
    *,
    provider: str,
    api_base: str | None,
    api_bases: dict[str, str | None] | None,
    profile_id: str | None,
    existing_api_base: str | None,
    existing_api_bases: dict[str, str] | None,
    existing_profile_id: str | None,
) -> tuple[str | None, dict[str, str] | None, str | None] | tuple[None, None, str | None]:
    """更新凭据时：endpoint 或 profile_id 出现在 PATCH 中才重算。"""
    if api_base is None and api_bases is None and profile_id is None:
        return (None, None, None)
    stored_base, stored_bases, stored_profile = normalize_credential_write_fields(
        provider=provider,
        profile_id=profile_id,
        api_base=api_base,
        api_bases=api_bases,
        existing_api_base=existing_api_base,
        existing_api_bases=existing_api_bases,
        existing_profile_id=existing_profile_id,
    )
    patch_base = stored_base if api_base is not None or profile_id is not None or api_bases is not None else None
    patch_bases = stored_bases if api_base is not None or profile_id is not None or api_bases is not None else None
    patch_profile = stored_profile if profile_id is not None else None
    return (patch_base, patch_bases, patch_profile)


class CredentialWritesMixin:
    """写侧 mixin — 由 GatewayManagementWriteService 组合。"""

    async def create_virtual_key(self, *, tenant_id: uuid.UUID, created_by_user_id: uuid.UUID | None, name: str, description: str | None, key_id_str: str, key_hash: str, encrypted_key: str, allowed_models: list[str], allowed_capabilities: list[str], rpm_limit: int | None, tpm_limit: int | None, store_full_messages: bool, guardrail_enabled: bool, expires_at: datetime | None) -> Any:
        assert_vkey_guardrail_create_allowed(
            global_guardrail_enabled=settings.gateway_default_guardrail_enabled,
            requested_guardrail_enabled=guardrail_enabled,
        )
        return await self._vkeys.create(tenant_id=tenant_id, created_by_user_id=created_by_user_id, name=name, description=description, key_id_str=key_id_str, key_hash=key_hash, encrypted_key=encrypted_key, allowed_models=allowed_models, allowed_capabilities=allowed_capabilities, rpm_limit=rpm_limit, tpm_limit=tpm_limit, store_full_messages=store_full_messages, guardrail_enabled=guardrail_enabled, expires_at=expires_at)

    async def revoke_virtual_key(self, key_id: uuid.UUID, *, tenant_id: uuid.UUID, actor_user_id: uuid.UUID | None, team_role: str, is_platform_admin: bool) -> None:
        record = await self._vkeys.get(key_id)
        assert_virtual_key_accessible_by_actor(
            record,
            key_id=str(key_id),
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            require_active=False,
        )
        await self._vkeys.revoke(key_id)

    async def revoke_virtual_keys_batch(self, key_ids: list[uuid.UUID], *, tenant_id: uuid.UUID, actor_user_id: uuid.UUID | None, team_role: str, is_platform_admin: bool) -> tuple[list[uuid.UUID], list[tuple[uuid.UUID, VirtualKeyBatchRevokeReason]]]:
        revoked: list[uuid.UUID] = []
        failed: list[tuple[uuid.UUID, VirtualKeyBatchRevokeReason]] = []
        seen: set[uuid.UUID] = set()
        for key_id in key_ids:
            if key_id in seen:
                continue
            seen.add(key_id)
            try:
                await self.revoke_virtual_key(key_id, tenant_id=tenant_id, actor_user_id=actor_user_id, team_role=team_role, is_platform_admin=is_platform_admin)
            except VirtualKeyNotFoundError:
                failed.append((key_id, 'not_found'))
            except SystemVirtualKeyRevokeForbiddenError:
                failed.append((key_id, 'system_key'))
            except TeamPermissionDeniedError:
                failed.append((key_id, 'permission_denied'))
            else:
                revoked.append(key_id)
        return (revoked, failed)

    async def create_team_credential(
        self,
        *,
        tenant_id: uuid.UUID,
        provider: str,
        name: str,
        api_key_encrypted: str,
        api_base: str | None,
        api_bases: dict[str, str | None] | None,
        profile_id: str | None,
        extra: dict[str, Any] | None,
    ) -> CredentialReadModel:
        stored_base, stored_bases, stored_profile = normalize_credential_write_fields(
            provider=provider,
            profile_id=profile_id,
            api_base=api_base,
            api_bases=api_bases,
        )
        row = await self._creds.create_for_tenant(
            tenant_id=tenant_id,
            provider=provider,
            name=name,
            api_key_encrypted=api_key_encrypted,
            api_base=stored_base,
            api_bases=stored_bases,
            profile_id=stored_profile,
            extra=extra,
        )
        await self.reload_litellm_router()
        return ensure_credential_read_model(row)

    async def create_system_credential(
        self,
        *,
        is_platform_admin: bool,
        provider: str,
        name: str,
        api_key_encrypted: str,
        api_base: str | None,
        api_bases: dict[str, str | None] | None,
        profile_id: str | None,
        extra: dict[str, Any] | None,
    ) -> CredentialReadModel:
        from domains.gateway.domain.policies.credential_scope import (
            assert_system_credential_mutation_allowed,
        )

        assert_system_credential_mutation_allowed(is_platform_admin=is_platform_admin)
        stored_base, stored_bases, stored_profile = normalize_credential_write_fields(
            provider=provider,
            profile_id=profile_id,
            api_base=api_base,
            api_bases=api_bases,
        )
        row = await self._system_creds.create(
            provider=provider,
            name=name,
            api_key_encrypted=api_key_encrypted,
            api_base=stored_base,
            api_bases=stored_bases,
            profile_id=stored_profile,
            extra=extra,
        )
        await self.reload_litellm_router()
        return ensure_credential_read_model(row)

    async def update_managed_credential(
        self,
        credential_id: uuid.UUID,
        *,
        tenant_id: uuid.UUID,
        is_platform_admin: bool,
        api_key_encrypted: str | None,
        api_base: str | None,
        api_bases: dict[str, str | None] | None,
        profile_id: str | None,
        extra: dict[str, Any] | None,
        is_active: bool | None,
        name: str | None,
    ) -> CredentialReadModel:
        system_existing = await self._system_creds.get(credential_id)
        if system_existing is not None:
            from domains.gateway.domain.policies.credential_scope import (
                assert_system_credential_mutation_allowed,
            )

            assert_system_credential_mutation_allowed(is_platform_admin=is_platform_admin)
            if name is not None and name != system_existing.name and is_config_managed_system_credential(
                scope="system", name=system_existing.name, extra=system_existing.extra
            ):
                raise ValidationError(
                    "配置同步托管的系统凭据不可重命名；请通过环境变量或 app.toml 管理密钥"
                )
            patch_base, patch_bases, patch_profile = _credential_update_api_fields(
                provider=system_existing.provider,
                api_base=api_base,
                api_bases=api_bases,
                profile_id=profile_id,
                existing_api_base=system_existing.api_base,
                existing_api_bases=system_existing.api_bases,
                existing_profile_id=system_existing.profile_id,
            )
            updated = await self._system_creds.update(
                credential_id,
                api_key_encrypted=api_key_encrypted,
                api_base=patch_base,
                api_bases=patch_bases,
                profile_id=patch_profile,
                extra=extra,
                is_active=is_active,
                name=name,
            )
            if updated is None:
                raise CredentialNotFoundError(str(credential_id))
            await self.reload_litellm_router()
            return ensure_credential_read_model(updated)

        existing = await self._creds.get(credential_id)
        if existing is None or existing.tenant_id is None or existing.tenant_id != tenant_id:
            raise CredentialNotFoundError(str(credential_id))
        patch_base, patch_bases, patch_profile = _credential_update_api_fields(
            provider=existing.provider,
            api_base=api_base,
            api_bases=api_bases,
            profile_id=profile_id,
            existing_api_base=existing.api_base,
            existing_api_bases=existing.api_bases,
            existing_profile_id=existing.profile_id,
        )
        updated = await self._creds.update(
            credential_id,
            api_key_encrypted=api_key_encrypted,
            api_base=patch_base,
            api_bases=patch_bases,
            profile_id=patch_profile,
            extra=extra,
            is_active=is_active,
            name=name,
        )
        if updated is None:
            raise CredentialNotFoundError(str(credential_id))
        await self.reload_litellm_router()
        return ensure_credential_read_model(updated)

    async def delete_managed_credential(self, credential_id: uuid.UUID, *, tenant_id: uuid.UUID, is_platform_admin: bool) -> None:
        system_existing = await self._system_creds.get(credential_id)
        if system_existing is not None:
            from domains.gateway.domain.policies.credential_scope import (
                assert_system_credential_mutation_allowed,
            )

            assert_system_credential_mutation_allowed(is_platform_admin=is_platform_admin)
            await self._cascade_delete_models_for_credential(credential_id)
            await self._system_creds.delete(credential_id)
            await self.reload_litellm_router()
            return

        existing = await self._creds.get(credential_id)
        if existing is None or existing.tenant_id is None or existing.tenant_id != tenant_id:
            raise CredentialNotFoundError(str(credential_id))
        await self._cascade_delete_models_for_credential(credential_id)
        await self._creds.delete(credential_id)
        await self.reload_litellm_router()

    async def import_user_credential_to_team(self, *, user_credential_id: uuid.UUID, tenant_id: uuid.UUID, actor_user_id: uuid.UUID, is_platform_admin: bool) -> CredentialReadModel:
        src = await self._creds.get(user_credential_id)
        if src is None or src.scope != 'user':
            raise CredentialNotFoundError(str(user_credential_id))
        if src.scope_id != actor_user_id and (not is_platform_admin):
            raise TeamPermissionDeniedError(str(tenant_id))
        new_cred = await self._creds.copy_to_team(user_credential_id, tenant_id)
        if new_cred is None:
            raise CredentialNotFoundError(str(user_credential_id))
        await self.reload_litellm_router()
        return ensure_credential_read_model(new_cred)

    async def import_all_user_credentials_to_team(self, *, actor_user_id: uuid.UUID, tenant_id: uuid.UUID) -> int:
        user_creds = await self._creds.list_for_user(actor_user_id)
        created = 0
        for cred in user_creds:
            copied = await self._creds.copy_to_team(cred.id, tenant_id)
            if copied is not None:
                created += 1
        if created > 0:
            await self.reload_litellm_router()
        return created

    async def create_user_credential(
        self,
        *,
        actor_user_id: uuid.UUID,
        provider: str,
        name: str,
        api_key_encrypted: str,
        api_base: str | None,
        api_bases: dict[str, str | None] | None,
        profile_id: str | None,
        extra: dict[str, Any] | None,
    ) -> CredentialReadModel:
        dup = await self._creds.find_user_by_provider_and_name(actor_user_id, provider, name)
        if dup is not None:
            raise CredentialNameConflictError(provider, name)
        stored_base, stored_bases, stored_profile = normalize_credential_write_fields(
            provider=provider,
            profile_id=profile_id,
            api_base=api_base,
            api_bases=api_bases,
        )
        row = await self._creds.create(
            scope='user',
            scope_id=actor_user_id,
            provider=provider,
            name=name,
            api_key_encrypted=api_key_encrypted,
            api_base=stored_base,
            api_bases=stored_bases,
            profile_id=stored_profile,
            extra=extra,
        )
        await self.reload_litellm_router()
        return ensure_credential_read_model(row)

    async def update_user_credential(
        self,
        credential_id: uuid.UUID,
        *,
        actor_user_id: uuid.UUID,
        api_key_encrypted: str | None,
        api_base: str | None,
        api_bases: dict[str, str | None] | None,
        profile_id: str | None,
        extra: dict[str, Any] | None,
        is_active: bool | None,
        name: str | None,
    ) -> CredentialReadModel:
        existing = await self._creds.get(credential_id)
        if existing is None or existing.scope != 'user' or existing.scope_id != actor_user_id:
            raise CredentialNotFoundError(str(credential_id))
        if name is not None and name != existing.name:
            dup = await self._creds.find_user_by_provider_and_name(actor_user_id, existing.provider, name)
            if dup is not None:
                raise CredentialNameConflictError(existing.provider, name)
        patch_base, patch_bases, patch_profile = _credential_update_api_fields(
            provider=existing.provider,
            api_base=api_base,
            api_bases=api_bases,
            profile_id=profile_id,
            existing_api_base=existing.api_base,
            existing_api_bases=existing.api_bases,
            existing_profile_id=existing.profile_id,
        )
        updated = await self._creds.update(
            credential_id,
            api_key_encrypted=api_key_encrypted,
            api_base=patch_base,
            api_bases=patch_bases,
            profile_id=patch_profile,
            extra=extra,
            is_active=is_active,
            name=name,
        )
        if updated is None:
            raise CredentialNotFoundError(str(credential_id))
        await self.reload_litellm_router()
        return ensure_credential_read_model(updated)

    async def delete_user_credential(self, credential_id: uuid.UUID, *, actor_user_id: uuid.UUID, reload_router: bool=True) -> None:
        existing = await self._creds.get(credential_id)
        if existing is None or existing.scope != 'user' or existing.scope_id != actor_user_id:
            raise CredentialNotFoundError(str(credential_id))
        await self._cascade_delete_models_for_credential(credential_id)
        await self._creds.delete(credential_id)
        if reload_router:
            await self.reload_litellm_router()
