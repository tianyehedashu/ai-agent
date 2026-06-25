"""Gateway 管理面变更应用服务（写侧分包；对外 API 不变）。"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any
import uuid

from bootstrap.config import settings
from domains.gateway.application.management.credential_copy_types import (
    CredentialImportFailure,
    ImportCredentialsWithModelsResult,
    ImportedCredentialItem,
    ImportedModelSummary,
    ModelImportFailure,
)
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
from domains.gateway.domain.policies.credential_copy_policy import CredentialCopyScope
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
    patch_base = (
        stored_base
        if api_base is not None or profile_id is not None or api_bases is not None
        else None
    )
    patch_bases = (
        stored_bases
        if api_base is not None or profile_id is not None or api_bases is not None
        else None
    )
    patch_profile = stored_profile if profile_id is not None else None
    return (patch_base, patch_bases, patch_profile)


class CredentialWritesMixin:
    """写侧 mixin — 由 GatewayManagementWriteService 组合。"""

    async def resolve_extra_vkey_grant_tenant_ids_for_actor(
        self,
        *,
        actor_user_id: uuid.UUID,
        bound_team_id: uuid.UUID,
        requested_tenant_ids: Sequence[uuid.UUID],
    ) -> list[uuid.UUID]:
        from domains.gateway.application.management.vkey_team_grant_policy import (
            resolve_extra_vkey_grant_tenant_ids,
        )

        return await resolve_extra_vkey_grant_tenant_ids(
            self._session,
            actor_user_id=actor_user_id,
            bound_team_id=bound_team_id,
            requested_tenant_ids=requested_tenant_ids,
        )

    async def list_active_grant_tenant_ids_for_vkey(
        self, vkey_id: uuid.UUID
    ) -> tuple[uuid.UUID, ...]:
        from domains.gateway.application.management.virtual_key_team_grant_reads import (
            list_active_grant_tenant_ids,
        )

        return await list_active_grant_tenant_ids(self._session, vkey_id)

    async def create_virtual_key(
        self,
        *,
        tenant_id: uuid.UUID,
        created_by_user_id: uuid.UUID | None,
        name: str,
        description: str | None,
        key_id_str: str,
        key_hash: str,
        encrypted_key: str,
        allowed_models: list[str],
        allowed_capabilities: list[str],
        rpm_limit: int | None,
        tpm_limit: int | None,
        store_full_messages: bool,
        guardrail_enabled: bool,
        expires_at: datetime | None,
        extra_granted_team_ids: Sequence[uuid.UUID] | None = None,
    ) -> Any:
        assert_vkey_guardrail_create_allowed(
            global_guardrail_enabled=settings.gateway_default_guardrail_enabled,
            requested_guardrail_enabled=guardrail_enabled,
        )
        record = await self._vkeys.create(
            tenant_id=tenant_id,
            created_by_user_id=created_by_user_id,
            name=name,
            description=description,
            key_id_str=key_id_str,
            key_hash=key_hash,
            encrypted_key=encrypted_key,
            allowed_models=allowed_models,
            allowed_capabilities=allowed_capabilities,
            rpm_limit=rpm_limit,
            tpm_limit=tpm_limit,
            store_full_messages=store_full_messages,
            guardrail_enabled=guardrail_enabled,
            expires_at=expires_at,
        )
        if created_by_user_id is not None and not record.is_system:
            from domains.gateway.application.management.virtual_key_team_grant_writes import (
                ensure_self_grant_for_vkey,
            )

            await ensure_self_grant_for_vkey(
                self._session,
                vkey_id=record.id,
                tenant_id=tenant_id,
                granted_by_user_id=created_by_user_id,
            )
            if extra_granted_team_ids:
                from domains.gateway.application.management.virtual_key_team_grant_writes import (
                    grant_vkey_to_teams,
                )

                await grant_vkey_to_teams(
                    self._session,
                    vkey_id=record.id,
                    vkey_tenant_id=tenant_id,
                    tenant_ids=extra_granted_team_ids,
                    granted_by_user_id=created_by_user_id,
                )
        return record

    async def revoke_virtual_key(
        self,
        key_id: uuid.UUID,
        *,
        tenant_id: uuid.UUID,
        actor_user_id: uuid.UUID | None,
        team_role: str,
        is_platform_admin: bool,
    ) -> None:
        record = await self._vkeys.get(key_id)
        assert_virtual_key_accessible_by_actor(
            record,
            key_id=str(key_id),
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            require_active=False,
        )
        await self._vkeys.revoke(key_id)

    async def revoke_virtual_keys_batch(
        self,
        key_ids: list[uuid.UUID],
        *,
        tenant_id: uuid.UUID,
        actor_user_id: uuid.UUID | None,
        team_role: str,
        is_platform_admin: bool,
    ) -> tuple[list[uuid.UUID], list[tuple[uuid.UUID, VirtualKeyBatchRevokeReason]]]:
        revoked: list[uuid.UUID] = []
        failed: list[tuple[uuid.UUID, VirtualKeyBatchRevokeReason]] = []
        seen: set[uuid.UUID] = set()
        for key_id in key_ids:
            if key_id in seen:
                continue
            seen.add(key_id)
            try:
                await self.revoke_virtual_key(
                    key_id,
                    tenant_id=tenant_id,
                    actor_user_id=actor_user_id,
                    team_role=team_role,
                    is_platform_admin=is_platform_admin,
                )
            except VirtualKeyNotFoundError:
                failed.append((key_id, "not_found"))
            except SystemVirtualKeyRevokeForbiddenError:
                failed.append((key_id, "system_key"))
            except TeamPermissionDeniedError:
                failed.append((key_id, "permission_denied"))
            else:
                revoked.append(key_id)
        return (revoked, failed)

    async def create_team_credential(
        self,
        *,
        tenant_id: uuid.UUID,
        created_by_user_id: uuid.UUID,
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
            created_by_user_id=created_by_user_id,
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
        actor_user_id: uuid.UUID | None,
        team_role: str,
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
            previous_is_active = system_existing.is_active
            if (
                name is not None
                and name != system_existing.name
                and is_config_managed_system_credential(
                    scope="system", name=system_existing.name, extra=system_existing.extra
                )
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
            if is_active is not None and is_active != previous_is_active:
                await self._cascade_sync_models_for_credential_is_active(
                    credential_id,
                    is_active=is_active,
                )
            await self.reload_litellm_router()
            return ensure_credential_read_model(updated)

        existing = await self._creds.get(credential_id)
        if existing is None or existing.tenant_id is None or existing.tenant_id != tenant_id:
            raise CredentialNotFoundError(str(credential_id))
        from domains.gateway.domain.team_credential_access import (
            assert_team_credential_writable_by_actor,
        )

        assert_team_credential_writable_by_actor(
            existing,
            credential_id=credential_id,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            team_role=team_role,
            is_platform_admin=is_platform_admin,
        )
        previous_is_active = existing.is_active
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
        if is_active is not None and is_active != previous_is_active:
            await self._cascade_sync_models_for_credential_is_active(
                credential_id,
                is_active=is_active,
            )
        await self.reload_litellm_router()
        return ensure_credential_read_model(updated)

    async def delete_managed_credential(
        self,
        credential_id: uuid.UUID,
        *,
        tenant_id: uuid.UUID,
        actor_user_id: uuid.UUID | None,
        team_role: str,
        is_platform_admin: bool,
    ) -> None:
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
        from domains.gateway.domain.team_credential_access import (
            assert_team_credential_writable_by_actor,
        )

        assert_team_credential_writable_by_actor(
            existing,
            credential_id=credential_id,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            team_role=team_role,
            is_platform_admin=is_platform_admin,
        )
        await self._cascade_delete_models_for_credential(credential_id)
        await self._creds.delete(credential_id)
        await self.reload_litellm_router()

    async def import_user_credential_to_team(
        self,
        *,
        user_credential_id: uuid.UUID,
        tenant_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        is_platform_admin: bool,
    ) -> CredentialReadModel:
        src = await self._creds.get(user_credential_id)
        if src is None or src.scope != "user":
            raise CredentialNotFoundError(str(user_credential_id))
        if src.scope_id != actor_user_id and (not is_platform_admin):
            raise TeamPermissionDeniedError(str(tenant_id))
        new_cred = await self._creds.copy_to_team(
            user_credential_id,
            tenant_id,
            created_by_user_id=actor_user_id,
        )
        if new_cred is None:
            raise CredentialNotFoundError(str(user_credential_id))
        await self.reload_litellm_router()
        return ensure_credential_read_model(new_cred)

    async def import_credentials_with_models_to_team(
        self,
        *,
        credential_ids: list[uuid.UUID],
        tenant_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        is_platform_admin: bool,
        destination_team_role: str,
    ) -> ImportCredentialsWithModelsResult:
        """Copy user-scope credentials and their associated personal models to a target team."""
        return await self.copy_credentials_with_models(
            credential_ids=credential_ids,
            source=CredentialCopyScope(kind="personal"),
            destination=CredentialCopyScope(kind="team", team_id=tenant_id),
            actor_user_id=actor_user_id,
            is_platform_admin=is_platform_admin,
            source_team_role=None,
            destination_team_role=destination_team_role,
        )

    async def copy_credentials_with_models(
        self,
        *,
        credential_ids: list[uuid.UUID],
        source: CredentialCopyScope,
        destination: CredentialCopyScope,
        actor_user_id: uuid.UUID,
        is_platform_admin: bool,
        source_team_role: str | None,
        destination_team_role: str | None,
    ) -> ImportCredentialsWithModelsResult:
        """Copy credentials and associated models between personal / team scopes.

        .. deprecated::
            请改用 ``POST /api/v1/gateway/resource-grants`` 共享同一行 BYOK 资源，
            避免复制导致上游配额桶拆分。
        """
        from domains.gateway.domain.policies.credential_copy_policy import (
            assert_copy_endpoints_valid,
            assert_credential_copy_destination_allowed,
            credential_copy_failure_reason,
        )

        assert_copy_endpoints_valid(source=source, destination=destination)
        assert_credential_copy_destination_allowed(
            destination=destination,
            destination_team_role=destination_team_role,
            is_platform_admin=is_platform_admin,
        )

        personal_team_id = await self._ensure_personal_tenant_id(actor_user_id)
        source_models_tenant_id = (
            personal_team_id if source.kind == "personal" else source.team_id
        )
        assert source_models_tenant_id is not None

        permission_denied_tenant_id = (
            destination.team_id
            if destination.kind == "team" and destination.team_id is not None
            else personal_team_id
        )

        succeeded: list[ImportedCredentialItem] = []
        failed: list[CredentialImportFailure] = []
        any_created = False

        for cred_id in credential_ids:
            try:
                item = await self._copy_one_credential_with_models(
                    cred_id=cred_id,
                    source=source,
                    destination=destination,
                    actor_user_id=actor_user_id,
                    is_platform_admin=is_platform_admin,
                    source_team_role=source_team_role,
                    source_models_tenant_id=source_models_tenant_id,
                    personal_team_id=personal_team_id,
                    permission_denied_tenant_id=permission_denied_tenant_id,
                )
                succeeded.append(item)
                any_created = True
            except Exception as exc:
                reason = credential_copy_failure_reason(exc)
                failed.append(CredentialImportFailure(credential_id=str(cred_id), reason=reason))
                logger.warning(
                    "copy_credentials_with_models: cred=%s failed: %s",
                    cred_id,
                    str(exc) or type(exc).__name__,
                )

        if any_created:
            await self.reload_litellm_router()

        return ImportCredentialsWithModelsResult(succeeded=succeeded, failed=failed)

    async def _copy_one_credential_with_models(
        self,
        *,
        cred_id: uuid.UUID,
        source: CredentialCopyScope,
        destination: CredentialCopyScope,
        actor_user_id: uuid.UUID,
        is_platform_admin: bool,
        source_team_role: str | None,
        source_models_tenant_id: uuid.UUID,
        personal_team_id: uuid.UUID,
        permission_denied_tenant_id: uuid.UUID,
    ) -> ImportedCredentialItem:
        from domains.gateway.domain.policies.credential_copy_policy import (
            assert_credential_copy_source_allowed,
            credential_copy_failure_reason,
        )

        src = await self._creds.get(cred_id)
        if src is None:
            raise CredentialNotFoundError(str(cred_id))

        assert_credential_copy_source_allowed(
            src,
            source=source,
            actor_user_id=actor_user_id,
            is_platform_admin=is_platform_admin,
            source_team_role=source_team_role,
            permission_denied_tenant_id=permission_denied_tenant_id,
        )

        target_name = await self._unique_copy_credential_name(
            src,
            destination=destination,
            actor_user_id=actor_user_id,
        )

        new_cred = await self._copy_credential_to_destination(
            cred_id,
            destination=destination,
            actor_user_id=actor_user_id,
            name_override=target_name,
        )
        if new_cred is None:
            raise CredentialNotFoundError(str(cred_id))

        source_models = await self._models.list_tenant_owned(
            source_models_tenant_id, credential_id=cred_id, only_enabled=False
        )

        models_created: list[ImportedModelSummary] = []
        models_failed: list[ModelImportFailure] = []

        dest_models_tenant_id = (
            personal_team_id
            if destination.kind == "personal"
            else destination.team_id
        )
        assert dest_models_tenant_id is not None

        for pm in source_models:
            try:
                from domains.gateway.application.management.write_modules.model_writes import (
                    generate_unique_model_name,
                )

                unique_name = await generate_unique_model_name(
                    lambda n, _tid=dest_models_tenant_id: self._models.name_exists_for_tenant(
                        _tid, n
                    ),
                    pm.name,
                )
                await self._models.create(
                    tenant_id=dest_models_tenant_id,
                    name=unique_name,
                    capability=pm.capability,
                    real_model=pm.real_model,
                    credential_id=new_cred.id,
                    provider=pm.provider,
                    weight=pm.weight or 1,
                    rpm_limit=pm.rpm_limit,
                    tpm_limit=pm.tpm_limit,
                    tags=pm.tags,
                    upstream_call_shape=pm.upstream_call_shape,
                    enabled=pm.enabled,
                    created_by_user_id=actor_user_id,
                )
                models_created.append(
                    ImportedModelSummary(
                        source_model_id=str(pm.id),
                        name=unique_name,
                        real_model=pm.real_model,
                    )
                )
            except Exception as exc:
                models_failed.append(
                    ModelImportFailure(
                        model_name=pm.name, reason=credential_copy_failure_reason(exc)
                    )
                )
                logger.warning(
                    "copy_credentials_with_models: model=%s failed: %s",
                    pm.name,
                    str(exc),
                )

        return ImportedCredentialItem(
            source_credential_id=cred_id,
            new_credential_id=new_cred.id,
            new_credential_name=new_cred.name,
            new_credential_read=ensure_credential_read_model(new_cred),
            provider=new_cred.provider,
            models_created=models_created,
            models_failed=models_failed,
        )

    async def _unique_copy_credential_name(
        self,
        src: object,
        *,
        destination: CredentialCopyScope,
        actor_user_id: uuid.UUID,
    ) -> str:
        provider = getattr(src, "provider", "")
        name = getattr(src, "name", "")
        existing = None
        if destination.kind == "personal":
            existing = await self._creds.find_user_by_provider_and_name(
                actor_user_id, provider, name
            )
        elif destination.team_id is not None:
            existing = await self._creds.find_tenant_by_provider_and_name(
                destination.team_id, provider, name
            )
        if existing is not None:
            suffix = uuid.uuid4().hex[:4]
            return f"{name}-imported-{suffix}"
        return name

    async def _copy_credential_to_destination(
        self,
        cred_id: uuid.UUID,
        *,
        destination: CredentialCopyScope,
        actor_user_id: uuid.UUID,
        name_override: str,
    ):
        if destination.kind == "personal":
            return await self._creds.copy_to_user(
                cred_id,
                actor_user_id,
                created_by_user_id=actor_user_id,
                name_override=name_override,
            )
        assert destination.team_id is not None
        return await self._creds.copy_to_team(
            cred_id,
            destination.team_id,
            created_by_user_id=actor_user_id,
            name_override=name_override,
        )

    @staticmethod
    async def _unique_model_name_for_tenant(
        model_repo: Any, tenant_id: uuid.UUID, base: str
    ) -> str:
        """Deprecated: use :func:`generate_unique_model_name` from model_writes."""
        from domains.gateway.application.management.write_modules.model_writes import (
            generate_unique_model_name,
        )

        return await generate_unique_model_name(
            lambda n: model_repo.name_exists_for_tenant(tenant_id, n), base
        )

    async def import_all_user_credentials_to_team(
        self, *, actor_user_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> int:
        user_creds = await self._creds.list_for_user(actor_user_id)
        created = 0
        for cred in user_creds:
            copied = await self._creds.copy_to_team(
                cred.id,
                tenant_id,
                created_by_user_id=actor_user_id,
            )
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
            scope="user",
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
        if existing is None or existing.scope != "user" or existing.scope_id != actor_user_id:
            raise CredentialNotFoundError(str(credential_id))
        previous_is_active = existing.is_active
        if name is not None and name != existing.name:
            dup = await self._creds.find_user_by_provider_and_name(
                actor_user_id, existing.provider, name
            )
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
        if is_active is not None and is_active != previous_is_active:
            await self._cascade_sync_models_for_credential_is_active(
                credential_id,
                is_active=is_active,
            )
        await self.reload_litellm_router()
        return ensure_credential_read_model(updated)

    async def delete_user_credential(
        self, credential_id: uuid.UUID, *, actor_user_id: uuid.UUID, reload_router: bool = True
    ) -> None:
        existing = await self._creds.get(credential_id)
        if existing is None or existing.scope != "user" or existing.scope_id != actor_user_id:
            raise CredentialNotFoundError(str(credential_id))
        tenant_models = await self._models.list_by_credential_id(credential_id)
        system_models = await self._models.list_system(
            credential_id=credential_id,
            only_enabled=False,
        )
        model_ids = [m.id for m in (*tenant_models, *system_models)]
        from domains.gateway.application.resource_grant_cleanup import (
            purge_resource_grants_for_subjects,
        )

        await purge_resource_grants_for_subjects(
            self._session,
            subjects=[
                ("credential", [credential_id]),
                ("model", model_ids),
            ],
        )
        await self._cascade_delete_models_for_credential(credential_id)
        await self._creds.delete(credential_id)
        if reload_router:
            await self.reload_litellm_router()
