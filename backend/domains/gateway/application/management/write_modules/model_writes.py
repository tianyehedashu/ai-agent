"""Gateway 管理面变更应用服务（写侧分包；对外 API 不变）。"""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from typing import Any
import uuid

from domains.gateway.application.catalog.gateway_model_tags_pipeline import build_gateway_model_tags
from domains.gateway.application.litellm_real_model_prefix import litellm_prefix_violation_message
from domains.gateway.application.management.credential_read_mappers import (
    bindable_credential_scope,
)
from domains.gateway.application.management.multi_credential_types import (
    MultiCredentialGatewayModelResult,
)
from domains.gateway.application.model_reference_prune import (
    prune_gateway_model_name_references,
    prune_gateway_model_orphan_records,
    rename_gateway_model_name_references,
)
from domains.gateway.application.routing_strategy_validation import validate_routing_strategy
from domains.gateway.domain.errors import (
    CredentialNotFoundError,
    ManagementEntityNotFoundError,
)
from domains.gateway.domain.litellm_capability_mapping import strip_litellm_capability_tags
from domains.gateway.domain.litellm_model_id import build_litellm_model_id
from domains.gateway.domain.policies.credential_scope import (
    assert_system_credential_mutation_allowed,
    registry_target_for_credential_scope,
    team_model_credential_scope_allowed,
)
from domains.gateway.domain.types import (
    CONFIG_MANAGED_BY,
    GATEWAY_MODEL_MANAGED_BY_TAG,
    PERSONAL_MODEL_PROVIDERS,
    PERSONAL_MODEL_TYPES,
    is_config_managed_system_gateway_model,
)
from libs.exceptions import HttpMappableDomainError, ValidationError
from utils.logging import get_logger

logger = get_logger(__name__)

_BATCH_MODEL_OP_MAX = 200


@dataclass(frozen=True)
class GatewayModelBatchOperationFailure:
    id: uuid.UUID
    code: str
    message: str


@dataclass(frozen=True)
class GatewayModelBatchDeleteResult:
    succeeded: list[uuid.UUID]
    failed: list[GatewayModelBatchOperationFailure]
    grants_removed: int = 0
    budgets_removed: int = 0


@dataclass(frozen=True)
class GatewayModelBatchResyncCapabilitiesResult:
    succeeded: list[uuid.UUID]
    failed: list[GatewayModelBatchOperationFailure]


@dataclass(frozen=True)
class _PreparedGatewayModelWrite:
    normalized_real_model: str
    enriched_tags: dict[str, Any]


def _prepare_gateway_model_write_fields(
    *,
    provider: str,
    real_model: str,
    tags: dict[str, Any] | None,
    credential_provider: str,
) -> _PreparedGatewayModelWrite:
    raw_rm = str(real_model).strip()
    if not raw_rm:
        raise ValidationError("上游模型 ID 不能为空")
    prov_norm = provider.strip().lower()
    if credential_provider.strip().lower() != prov_norm:
        raise ValidationError(
            f"凭据提供商为 {credential_provider}，与请求的 provider {provider} 不一致"
        )
    prefix_msg = litellm_prefix_violation_message(provider, raw_rm)
    if prefix_msg:
        raise ValidationError(prefix_msg)
    normalized_rm = build_litellm_model_id(provider, raw_rm)
    enriched_tags = build_gateway_model_tags(
        tags,
        provider=provider,
        real_model=normalized_rm,
        skip_hints=is_config_managed_system_gateway_model(tags=tags),
    )
    return _PreparedGatewayModelWrite(
        normalized_real_model=normalized_rm,
        enriched_tags=enriched_tags,
    )


class ModelWritesMixin:
    """写侧 mixin — 由 GatewayManagementWriteService 组合。"""

    async def _assert_team_model_mutation_allowed(
        self,
        *,
        credential_id: uuid.UUID,
        tenant_id: uuid.UUID,
        actor_user_id: uuid.UUID | None,
        team_role: str,
        is_platform_admin: bool,
        mutation: str,
    ) -> None:
        from domains.gateway.domain.policies.team_model_access import (
            assert_can_create_model_on_team_credential,
            assert_can_delete_team_model_on_credential,
            assert_can_update_team_model_on_credential,
        )

        cred_row = await self._creds.get(credential_id)
        if cred_row is None:
            raise CredentialNotFoundError(str(credential_id))
        if cred_row.tenant_id is None or cred_row.scope == "user":
            return
        if cred_row.tenant_id != tenant_id:
            raise CredentialNotFoundError(str(credential_id))
        if mutation == "create":
            assert_can_create_model_on_team_credential(
                cred_row,
                actor_user_id=actor_user_id,
                team_role=team_role,
                is_platform_admin=is_platform_admin,
            )
        elif mutation == "update":
            assert_can_update_team_model_on_credential(
                cred_row,
                actor_user_id=actor_user_id,
                team_role=team_role,
                is_platform_admin=is_platform_admin,
            )
        else:
            assert_can_delete_team_model_on_credential(
                cred_row,
                actor_user_id=actor_user_id,
                team_role=team_role,
                is_platform_admin=is_platform_admin,
            )

    async def create_personal_models(self, user_id: uuid.UUID, *, display_name: str, provider: str, model_id: str, credential_id: uuid.UUID, model_types: list[str], tags: dict[str, Any] | None=None, enabled: bool=True, reload_router: bool=True) -> list[Any]:
        from domains.gateway.application.personal_models import (
            capability_for_model_type,
            personal_model_alias,
            tags_for_model_type,
        )
        if provider not in PERSONAL_MODEL_PROVIDERS:
            raise ValidationError(f'不支持的提供商: {provider}')
        if not model_types:
            raise ValidationError('model_types 不能为空')
        invalid = set(model_types) - PERSONAL_MODEL_TYPES
        if invalid:
            raise ValidationError(f'无效的模型类型: {sorted(invalid)}')
        await self._assert_user_owns_credential(user_id, credential_id)
        cred_row = await self._creds.get(credential_id)
        if cred_row is None:
            raise CredentialNotFoundError(str(credential_id))
        if cred_row.provider.strip().lower() != provider.strip().lower():
            raise ValidationError(f'凭据提供商为 {cred_row.provider}，与所选 provider {provider} 不一致')
        tenant_id = await self._ensure_personal_tenant_id(user_id)
        real_model = build_litellm_model_id(provider, model_id)
        created: list[Any] = []
        for idx, mtype in enumerate(model_types):
            cap = capability_for_model_type(mtype)
            alias = personal_model_alias(display_name, mtype, suffix=idx if idx else 0)
            suffix = 0
            while await self._models.name_exists_for_tenant(tenant_id, alias):
                suffix += 1
                alias = personal_model_alias(display_name, mtype, suffix=suffix)
            mtags = tags_for_model_type(mtype)
            mtags['display_name'] = display_name
            if tags:
                mtags.update({k: v for k, v in tags.items() if v is not None})
            mtags = build_gateway_model_tags(mtags, provider=provider, real_model=real_model)
            row = await self._models.create(tenant_id=tenant_id, name=alias, capability=cap, real_model=real_model, credential_id=credential_id, provider=provider, weight=1, rpm_limit=None, tpm_limit=None, tags=mtags, enabled=enabled)
            created.append(row)
        if reload_router:
            await self.reload_litellm_router(tenant_id=tenant_id)
        return created

    async def update_personal_model(self, user_id: uuid.UUID, model_id: uuid.UUID, fields: dict[str, Any]) -> Any:
        tenant_id = await self._ensure_personal_tenant_id(user_id)
        existing = await self._models.get_for_tenant(model_id, tenant_id)
        if existing is None:
            raise ManagementEntityNotFoundError('model', str(model_id))
        update_fields: dict[str, Any] = {}
        if 'credential_id' in fields and fields['credential_id'] is not None:
            await self._assert_user_owns_credential(user_id, fields['credential_id'])
            nrow = await self._creds.get(fields['credential_id'])
            if nrow is None:
                raise CredentialNotFoundError(str(fields['credential_id']))
            if nrow.provider.strip().lower() != existing.provider.strip().lower():
                raise ValidationError(f'凭据提供商为 {nrow.provider}，与当前模型的 provider（{existing.provider}）不一致')
            update_fields['credential_id'] = fields['credential_id']
        if fields.get('model_id') is not None:
            update_fields['real_model'] = build_litellm_model_id(existing.provider, str(fields['model_id']))
        if fields.get('is_active') is not None:
            update_fields['enabled'] = fields['is_active']
        if fields.get('display_name') is not None:
            merged_tags = dict(existing.tags or {})
            merged_tags['display_name'] = fields['display_name']
            update_fields['tags'] = merged_tags
        if not update_fields:
            return existing
        updated = await self._models.update(model_id, **update_fields)
        if updated is None:
            raise ManagementEntityNotFoundError('model', str(model_id))
        await self.reload_litellm_router(tenant_id=tenant_id)
        return updated

    async def delete_personal_model(self, user_id: uuid.UUID, model_id: uuid.UUID) -> None:
        tenant_id = await self._ensure_personal_tenant_id(user_id)
        existing = await self._models.get_for_tenant(model_id, tenant_id)
        if existing is None:
            raise ManagementEntityNotFoundError('model', str(model_id))
        model_name = existing.name
        await self._models.delete(model_id)
        await self._finalize_gateway_model_deletions(
            deleted_ids=frozenset({model_id}),
            deleted_names=frozenset({model_name}),
            tenant_id=tenant_id,
        )

    async def delete_personal_models_batch(
        self,
        user_id: uuid.UUID,
        model_ids: list[uuid.UUID],
    ) -> GatewayModelBatchDeleteResult:
        tenant_id = await self._ensure_personal_tenant_id(user_id)
        return await self.delete_gateway_models_batch(
            model_ids,
            tenant_id=tenant_id,
            actor_user_id=user_id,
            team_role="owner",
            is_platform_admin=False,
        )

    async def create_gateway_model(
        self,
        *,
        tenant_id: uuid.UUID,
        name: str,
        capability: str,
        real_model: str,
        credential_id: uuid.UUID,
        provider: str,
        weight: int,
        rpm_limit: int | None,
        tpm_limit: int | None,
        tags: dict[str, Any] | None,
        upstream_call_shape: str | None = None,
        actor_user_id: uuid.UUID | None,
        team_role: str,
        is_platform_admin: bool,
        enabled: bool = True,
        reload_router: bool = True,
    ) -> Any:
        cred = await self._creds.get_bindable_for_team_gateway_model(
            credential_id, tenant_id=tenant_id, is_platform_admin=is_platform_admin
        )
        if cred is None:
            raise CredentialNotFoundError(str(credential_id))
        from domains.gateway.domain.policies.team_model_access import (
            assert_can_create_model_on_team_credential,
        )
        from domains.gateway.infrastructure.models.provider_credential import (
            ProviderCredential,
        )

        if isinstance(cred, ProviderCredential):
            assert_can_create_model_on_team_credential(
                cred,
                actor_user_id=actor_user_id,
                team_role=team_role,
                is_platform_admin=is_platform_admin,
            )
        if not team_model_credential_scope_allowed(bindable_credential_scope(cred)):
            raise ValidationError(
                '系统凭据注册的模型应写入 system_gateway_models；'
                '请使用 create_system_gateway_model 或系统凭据批量导入'
            )
        prepared = _prepare_gateway_model_write_fields(
            provider=provider,
            real_model=real_model,
            tags=tags,
            credential_provider=cred.provider,
        )
        row = await self._models.create(
            tenant_id=tenant_id,
            name=name,
            capability=capability,
            real_model=prepared.normalized_real_model,
            credential_id=credential_id,
            provider=provider,
            weight=weight,
            rpm_limit=rpm_limit,
            tpm_limit=tpm_limit,
            tags=prepared.enriched_tags,
            upstream_call_shape=upstream_call_shape,
            enabled=enabled,
        )
        if reload_router:
            await self.reload_litellm_router(tenant_id=tenant_id)
        return row

    async def create_system_gateway_model(
        self,
        *,
        name: str,
        capability: str,
        real_model: str,
        credential_id: uuid.UUID,
        provider: str,
        weight: int,
        rpm_limit: int | None,
        tpm_limit: int | None,
        tags: dict[str, Any] | None,
        upstream_call_shape: str | None = None,
        is_platform_admin: bool,
        enabled: bool = True,
        reload_router: bool = True,
    ) -> Any:
        assert_system_credential_mutation_allowed(is_platform_admin=is_platform_admin)
        cred = await self._system_creds.get(credential_id)
        if cred is None:
            raise CredentialNotFoundError(str(credential_id))
        prepared = _prepare_gateway_model_write_fields(
            provider=provider,
            real_model=real_model,
            tags=tags,
            credential_provider=cred.provider,
        )
        row = await self._models.create_system(
            name=name,
            capability=capability,
            real_model=prepared.normalized_real_model,
            credential_id=credential_id,
            provider=provider,
            weight=weight,
            rpm_limit=rpm_limit,
            tpm_limit=tpm_limit,
            tags=prepared.enriched_tags,
            upstream_call_shape=upstream_call_shape,
            enabled=enabled,
        )
        if reload_router:
            await self.reload_litellm_router()
        return row

    async def create_managed_gateway_model(
        self,
        *,
        credential_scope: str | None,
        tenant_id: uuid.UUID,
        name: str,
        capability: str,
        real_model: str,
        credential_id: uuid.UUID,
        provider: str,
        weight: int,
        rpm_limit: int | None,
        tpm_limit: int | None,
        tags: dict[str, Any] | None,
        upstream_call_shape: str | None = None,
        actor_user_id: uuid.UUID | None,
        team_role: str,
        is_platform_admin: bool,
        enabled: bool = True,
        reload_router: bool = True,
    ) -> Any:
        """按凭据 scope 写入 team 或 system 注册表（管理面统一入口）。"""
        if registry_target_for_credential_scope(credential_scope) == "system":
            return await self.create_system_gateway_model(
                name=name,
                capability=capability,
                real_model=real_model,
                credential_id=credential_id,
                provider=provider,
                weight=weight,
                rpm_limit=rpm_limit,
                tpm_limit=tpm_limit,
                tags=tags,
                upstream_call_shape=upstream_call_shape,
                is_platform_admin=is_platform_admin,
                enabled=enabled,
                reload_router=reload_router,
            )
        return await self.create_gateway_model(
            tenant_id=tenant_id,
            name=name,
            capability=capability,
            real_model=real_model,
            credential_id=credential_id,
            provider=provider,
            weight=weight,
            rpm_limit=rpm_limit,
            tpm_limit=tpm_limit,
            tags=tags,
            upstream_call_shape=upstream_call_shape,
            actor_user_id=actor_user_id,
            team_role=team_role,
            is_platform_admin=is_platform_admin,
            enabled=enabled,
            reload_router=reload_router,
        )

    async def create_multi_credential_gateway_model(
        self,
        *,
        tenant_id: uuid.UUID,
        name: str,
        capability: str,
        real_model: str,
        provider: str,
        credential_ids: list[uuid.UUID],
        actor_user_id: uuid.UUID | None,
        team_role: str,
        is_platform_admin: bool,
        strategy: str = 'simple-shuffle',
        weight: int = 1,
        rpm_limit: int | None = None,
        tpm_limit: int | None = None,
        tags: dict[str, Any] | None = None,
        upstream_call_shape: str | None = None,
        enabled: bool = True,
    ) -> MultiCredentialGatewayModelResult:
        """为同一 ``(provider, real_model)`` 在多个凭据上一键注册并生成 ``GatewayRoute``。

            - 每个 ``credential_id`` 都建一行 ``GatewayModel``，别名为 ``<name>--<credentialId 短哈希>``；
            - 自动创建 ``GatewayRoute(virtual_model=name, primary_models=[...all aliases])``，
              客户端调用 ``model=name`` 时由 Router 在多 deployment 间按 ``strategy`` 调度；
            - 与 Phase 2 ``_routes_to_virtual_deployments`` 联动后激活原生负载均衡（least-busy /
              cost-based / weighted-shuffle）。
            - 若 ``name`` 已被 ``GatewayModel`` / ``GatewayRoute`` 占用，全部回滚并抛 ``ValidationError``。
            """
        cleaned_name = (name or '').strip()
        if not cleaned_name:
            raise ValidationError('虚拟模型名不能为空')
        if not credential_ids:
            raise ValidationError('credential_ids 不能为空')
        if len(set(credential_ids)) != len(credential_ids):
            raise ValidationError('credential_ids 不能包含重复项')
        strategy_norm = validate_routing_strategy(strategy)
        repo = self._models
        if await repo.name_exists_for_tenant(tenant_id, cleaned_name):
            raise ValidationError(f'虚拟模型名 {cleaned_name} 与现有 GatewayModel 别名冲突')
        existing_route = await self._routes.get_by_virtual_model(tenant_id, cleaned_name)
        if existing_route is not None:
            raise ValidationError(f'虚拟模型名 {cleaned_name} 已存在 GatewayRoute')
        for cid in credential_ids:
            bindable = await self._creds.get_bindable_for_team_gateway_model(
                cid, tenant_id=tenant_id, is_platform_admin=is_platform_admin
            )
            if bindable is None:
                raise CredentialNotFoundError(str(cid))
            if not team_model_credential_scope_allowed(bindable_credential_scope(bindable)):
                raise ValidationError(
                    '多凭据注册不支持系统凭据；请使用系统模型单独注册或批量导入'
                )
        from domains.gateway.infrastructure.models.gateway_model import GatewayModel
        created_models: list[GatewayModel] = []
        route = None
        try:
            for cid in credential_ids:
                short = uuid.UUID(str(cid)).hex[:8]
                alias = f'{cleaned_name}--{short}'
                suffix = 0
                base_alias = alias
                while await repo.name_exists_for_tenant(tenant_id, alias):
                    suffix += 1
                    alias = f'{base_alias}-{suffix}'
                row = await self.create_gateway_model(
                    tenant_id=tenant_id,
                    name=alias,
                    capability=capability,
                    real_model=real_model,
                    credential_id=cid,
                    provider=provider,
                    weight=weight,
                    rpm_limit=rpm_limit,
                    tpm_limit=tpm_limit,
                    tags=tags,
                    upstream_call_shape=upstream_call_shape,
                    actor_user_id=actor_user_id,
                    team_role=team_role,
                    is_platform_admin=is_platform_admin,
                    enabled=enabled,
                    reload_router=False,
                )
                created_models.append(row)
            route = await self._routes.create(tenant_id=tenant_id, virtual_model=cleaned_name, primary_models=[m.name for m in created_models], strategy=strategy_norm)
        except Exception:
            for r in created_models:
                with suppress(Exception):
                    await repo.delete(r.id)
            raise
        await self.reload_litellm_router(tenant_id=tenant_id)
        assert route is not None
        return MultiCredentialGatewayModelResult(route=route, models=created_models)

    async def _apply_gateway_model_update_fields(
        self,
        *,
        model_id: uuid.UUID,
        existing: Any,
        owner_tenant_id: uuid.UUID | None,
        tenant_id: uuid.UUID,
        actor_user_id: uuid.UUID | None,
        team_role: str,
        is_platform_admin: bool,
        fields: dict[str, Any],
        block_config_managed_rename: bool,
    ) -> dict[str, Any]:
        repo = self._models
        update_fields = dict(fields)
        if 'credential_id' in update_fields and update_fields['credential_id'] is not None:
            new_cid_raw = update_fields['credential_id']
            new_cid = new_cid_raw if isinstance(new_cid_raw, uuid.UUID) else uuid.UUID(str(new_cid_raw))
            cred = await self._creds.get_bindable_for_team_gateway_model(
                new_cid, tenant_id=tenant_id, is_platform_admin=is_platform_admin
            )
            if cred is None:
                raise CredentialNotFoundError(str(new_cid))
            if owner_tenant_id is not None:
                await self._assert_team_model_mutation_allowed(
                    credential_id=new_cid,
                    tenant_id=tenant_id,
                    actor_user_id=actor_user_id,
                    team_role=team_role,
                    is_platform_admin=is_platform_admin,
                    mutation="create",
                )
            if owner_tenant_id is not None and not team_model_credential_scope_allowed(
                bindable_credential_scope(cred)
            ):
                raise ValidationError('团队模型不可绑定系统凭据')
            if cred.provider.strip().lower() != existing.provider.strip().lower():
                raise ValidationError(f'凭据提供商为 {cred.provider}，与当前模型的 provider（{existing.provider}）不一致')
        if 'real_model' in update_fields and update_fields['real_model'] is not None:
            raw_rm = str(update_fields['real_model']).strip()
            if not raw_rm:
                raise ValidationError('上游模型 ID 不能为空')
            prefix_msg = litellm_prefix_violation_message(existing.provider, raw_rm)
            if prefix_msg:
                raise ValidationError(prefix_msg)
            update_fields['real_model'] = build_litellm_model_id(existing.provider, raw_rm)
        resync_capabilities = bool(update_fields.pop('resync_capabilities', False))
        if resync_capabilities and is_config_managed_system_gateway_model(
            tags=existing.tags
        ):
            raise ValidationError('配置托管的系统模型不可从 LiteLLM 同步能力')
        if resync_capabilities or 'real_model' in update_fields or 'tags' in update_fields:
            merged_tags = dict(existing.tags or {})
            if isinstance(update_fields.get('tags'), dict):
                merged_tags.update(update_fields['tags'])
            if resync_capabilities:
                merged_tags = strip_litellm_capability_tags(merged_tags)
            real_for_tags = str(
                update_fields.get('real_model') or existing.real_model
            ).strip()
            update_fields['tags'] = build_gateway_model_tags(
                merged_tags,
                provider=existing.provider,
                real_model=real_for_tags,
                skip_hints=is_config_managed_system_gateway_model(tags=existing.tags),
                hint_mode='resync' if resync_capabilities else 'fill_missing',
            )
        new_name_raw = update_fields.get('name')
        if new_name_raw is not None:
            new_name = str(new_name_raw).strip()
            if not new_name:
                raise ValidationError('注册别名不能为空')
            update_fields['name'] = new_name
            if new_name != existing.name:
                if block_config_managed_rename:
                    raise ValidationError('配置托管的系统模型不可修改注册别名')
                if await repo.name_exists_in_scope(owner_tenant_id, new_name, exclude_id=model_id):
                    raise ValidationError(f'注册别名已存在: {new_name}')
                await rename_gateway_model_name_references(
                    self._session,
                    tenant_id=owner_tenant_id,
                    old_name=existing.name,
                    new_name=new_name,
                )
        return update_fields

    async def update_gateway_model(
        self,
        model_id: uuid.UUID,
        *,
        tenant_id: uuid.UUID,
        actor_user_id: uuid.UUID | None,
        team_role: str,
        is_platform_admin: bool,
        fields: dict[str, Any],
        reload_router: bool = True,
    ) -> Any:
        from domains.gateway.domain.policies.credential_scope import (
            assert_system_credential_mutation_allowed,
        )
        from domains.gateway.domain.types import is_config_managed_system_gateway_model

        repo = self._models
        existing = await repo.get(model_id)
        if existing is not None:
            if existing.tenant_id is not None and existing.tenant_id != tenant_id:
                raise ManagementEntityNotFoundError('model', str(model_id))
            await self._assert_team_model_mutation_allowed(
                credential_id=existing.credential_id,
                tenant_id=tenant_id,
                actor_user_id=actor_user_id,
                team_role=team_role,
                is_platform_admin=is_platform_admin,
                mutation='update',
            )
            tags = existing.tags or {}
            block_rename = (
                existing.tenant_id is None
                and tags.get(GATEWAY_MODEL_MANAGED_BY_TAG) == CONFIG_MANAGED_BY
            )
            update_fields = await self._apply_gateway_model_update_fields(
                model_id=model_id,
                existing=existing,
                owner_tenant_id=existing.tenant_id,
                tenant_id=tenant_id,
                actor_user_id=actor_user_id,
                team_role=team_role,
                is_platform_admin=is_platform_admin,
                fields=fields,
                block_config_managed_rename=block_rename,
            )
            updated = await repo.update(model_id, **update_fields)
            if updated is None:
                raise ManagementEntityNotFoundError('model', str(model_id))
            if reload_router:
                await self.reload_litellm_router(tenant_id=tenant_id)
            return updated

        system_existing = await repo.get_system(model_id)
        if system_existing is None:
            raise ManagementEntityNotFoundError('model', str(model_id))

        assert_system_credential_mutation_allowed(is_platform_admin=is_platform_admin)
        update_fields = await self._apply_gateway_model_update_fields(
            model_id=model_id,
            existing=system_existing,
            owner_tenant_id=None,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            team_role=team_role,
            is_platform_admin=is_platform_admin,
            fields=fields,
            block_config_managed_rename=is_config_managed_system_gateway_model(
                tags=system_existing.tags
            ),
        )
        updated = await repo.update_system(model_id, **update_fields)
        if updated is None:
            raise ManagementEntityNotFoundError('model', str(model_id))
        if reload_router:
            await self.reload_litellm_router()
        return updated

    async def _delete_gateway_model_row(
        self,
        model_id: uuid.UUID,
        *,
        tenant_id: uuid.UUID,
        actor_user_id: uuid.UUID | None,
        team_role: str,
        is_platform_admin: bool,
    ) -> tuple[uuid.UUID, str]:
        """删除单行并返回 (model_id, model_name)；不触发 prune / reload。"""
        repo = self._models
        existing = await repo.get(model_id)
        if existing is not None:
            if existing.tenant_id is not None and existing.tenant_id != tenant_id:
                raise ManagementEntityNotFoundError('model', str(model_id))
            await self._assert_team_model_mutation_allowed(
                credential_id=existing.credential_id,
                tenant_id=tenant_id,
                actor_user_id=actor_user_id,
                team_role=team_role,
                is_platform_admin=is_platform_admin,
                mutation='delete',
            )
            model_name = existing.name
            await repo.delete(model_id)
            return model_id, model_name

        system_existing = await repo.get_system(model_id)
        if system_existing is None:
            raise ManagementEntityNotFoundError('model', str(model_id))

        from domains.gateway.domain.policies.credential_scope import (
            assert_system_credential_mutation_allowed,
        )
        from domains.gateway.domain.types import is_config_managed_system_gateway_model

        assert_system_credential_mutation_allowed(is_platform_admin=is_platform_admin)
        if is_config_managed_system_gateway_model(tags=system_existing.tags):
            raise ValidationError(
                '配置同步托管的系统模型不可删除；请通过 gateway-catalog 或配置管理'
            )
        model_name = system_existing.name
        await repo.delete_system(model_id)
        return model_id, model_name

    @staticmethod
    def _batch_operation_failure(
        model_id: uuid.UUID,
        exc: BaseException,
    ) -> GatewayModelBatchOperationFailure:
        code = getattr(exc, 'code', None) or exc.__class__.__name__
        message = getattr(exc, 'message', None) or str(exc)
        return GatewayModelBatchOperationFailure(
            id=model_id,
            code=str(code),
            message=str(message),
        )

    async def _finalize_gateway_model_deletions(
        self,
        *,
        deleted_ids: frozenset[uuid.UUID],
        deleted_names: frozenset[str],
        tenant_id: uuid.UUID | None = None,
    ) -> tuple[int, int]:
        if not deleted_names:
            return 0, 0
        await prune_gateway_model_name_references(self._session, deleted_names)
        grants_removed, budgets_removed = await prune_gateway_model_orphan_records(
            self._session,
            model_ids=deleted_ids,
            model_names=deleted_names,
        )
        await self.reload_litellm_router(tenant_id=tenant_id)
        return grants_removed, budgets_removed

    async def delete_gateway_model(
        self,
        model_id: uuid.UUID,
        *,
        tenant_id: uuid.UUID,
        actor_user_id: uuid.UUID | None,
        team_role: str,
        is_platform_admin: bool = False,
    ) -> None:
        deleted_id, deleted_name = await self._delete_gateway_model_row(
            model_id,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            team_role=team_role,
            is_platform_admin=is_platform_admin,
        )
        await self._finalize_gateway_model_deletions(
            deleted_ids=frozenset({deleted_id}),
            deleted_names=frozenset({deleted_name}),
            tenant_id=tenant_id,
        )

    async def delete_gateway_models_batch(
        self,
        model_ids: list[uuid.UUID],
        *,
        tenant_id: uuid.UUID,
        actor_user_id: uuid.UUID | None,
        team_role: str,
        is_platform_admin: bool = False,
    ) -> GatewayModelBatchDeleteResult:
        if len(model_ids) > _BATCH_MODEL_OP_MAX:
            raise ValidationError(
                f'单次最多删除 {_BATCH_MODEL_OP_MAX} 个模型',
            )
        unique_ids = list(dict.fromkeys(model_ids))
        succeeded: list[uuid.UUID] = []
        failed: list[GatewayModelBatchOperationFailure] = []
        deleted_ids: set[uuid.UUID] = set()
        deleted_names: set[str] = set()

        for model_id in unique_ids:
            try:
                deleted_id, deleted_name = await self._delete_gateway_model_row(
                    model_id,
                    tenant_id=tenant_id,
                    actor_user_id=actor_user_id,
                    team_role=team_role,
                    is_platform_admin=is_platform_admin,
                )
            except (HttpMappableDomainError, ValidationError) as exc:
                failed.append(self._batch_operation_failure(model_id, exc))
                continue
            succeeded.append(deleted_id)
            deleted_ids.add(deleted_id)
            deleted_names.add(deleted_name)

        grants_removed = 0
        budgets_removed = 0
        if deleted_names:
            grants_removed, budgets_removed = await self._finalize_gateway_model_deletions(
                deleted_ids=frozenset(deleted_ids),
                deleted_names=frozenset(deleted_names),
                tenant_id=tenant_id,
            )

        return GatewayModelBatchDeleteResult(
            succeeded=succeeded,
            failed=failed,
            grants_removed=grants_removed,
            budgets_removed=budgets_removed,
        )

    async def resync_gateway_models_capabilities_batch(
        self,
        model_ids: list[uuid.UUID],
        *,
        tenant_id: uuid.UUID,
        actor_user_id: uuid.UUID | None,
        team_role: str,
        is_platform_admin: bool = False,
    ) -> GatewayModelBatchResyncCapabilitiesResult:
        if len(model_ids) > _BATCH_MODEL_OP_MAX:
            raise ValidationError(
                f'单次最多同步 {_BATCH_MODEL_OP_MAX} 个模型能力',
            )
        unique_ids = list(dict.fromkeys(model_ids))
        succeeded: list[uuid.UUID] = []
        failed: list[GatewayModelBatchOperationFailure] = []

        for model_id in unique_ids:
            try:
                await self.update_gateway_model(
                    model_id,
                    tenant_id=tenant_id,
                    actor_user_id=actor_user_id,
                    team_role=team_role,
                    is_platform_admin=is_platform_admin,
                    fields={'resync_capabilities': True},
                    reload_router=False,
                )
            except (HttpMappableDomainError, ValidationError) as exc:
                failed.append(self._batch_operation_failure(model_id, exc))
                continue
            succeeded.append(model_id)

        if succeeded:
            await self.reload_litellm_router(tenant_id=tenant_id)

        return GatewayModelBatchResyncCapabilitiesResult(
            succeeded=succeeded,
            failed=failed,
        )
