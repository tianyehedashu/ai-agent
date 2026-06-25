"""Gateway 管理面变更应用服务（写侧分包；对外 API 不变）。"""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
import uuid

if TYPE_CHECKING:
    from domains.gateway.application.management.model_copy_types import ModelCopyCredentialPlan

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
from domains.gateway.application.upstream_catalog_capability_prep import (
    prepare_gateway_write_from_upstream_catalog,
    should_apply_catalog_prep_to_base_tags,
)
from domains.gateway.domain.errors import (
    CredentialNotFoundError,
    ManagementEntityNotFoundError,
)
from domains.gateway.domain.litellm_capability_mapping import strip_litellm_capability_tags
from domains.gateway.domain.litellm_model_id import (
    normalize_gateway_stored_real_model,
    normalize_stored_real_model_for_credential,
)
from domains.gateway.domain.model_types_tags import (
    tags_from_model_types,
    validate_model_types_for_capability,
)
from domains.gateway.domain.policies.credential_scope import (
    assert_system_credential_mutation_allowed,
    registry_target_for_credential_scope,
    team_model_credential_scope_allowed,
)
from domains.gateway.domain.policies.deployment_weight import assert_deployment_weight
from domains.gateway.domain.types import (
    CONFIG_MANAGED_BY,
    GATEWAY_MODEL_MANAGED_BY_TAG,
    PERSONAL_MODEL_PROVIDERS,
    PERSONAL_MODEL_TYPES,
    GatewayCapability,
    is_config_managed_system_gateway_model,
)
from domains.gateway.domain.upstream_endpoint import credential_api_base
from libs.exceptions import HttpMappableDomainError, ValidationError
from utils.logging import get_logger

logger = get_logger(__name__)

_BATCH_MODEL_OP_MAX = 200
_ALLOWED_UPSTREAM_CALL_SHAPES = frozenset({"openai_compat", "anthropic_native"})


async def generate_unique_model_name(
    exists_fn: Any, base: str, *, max_len: int = 200
) -> str:
    """Generate a unique model name by appending numeric suffixes.

    Shared across ``CredentialWritesMixin``, ``CredentialUpstreamCatalogService``
    for both tenant-scoped and system-scoped model name deduplication.
    """
    name = base[:max_len]
    if not await exists_fn(name):
        return name
    for i in range(2, 10_000):
        suffix = f"-{i}"
        candidate = (base[: max_len - len(suffix)] + suffix).strip("-") or f"model-{i}"
        if not await exists_fn(candidate):
            return candidate
    raise ValidationError("无法生成唯一注册别名")


def _parse_gateway_capability(raw: str) -> str:
    key = raw.strip().lower()
    try:
        return GatewayCapability(key).value
    except ValueError as exc:
        raise ValidationError(f"不支持的 capability: {raw}") from exc


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
    catalog_capability: str | None = None


@dataclass(frozen=True)
class _ResyncTagsPrepResult:
    tags: dict[str, Any]
    capability: str | None = None


def _upstream_profile_id_from_credential(cred: object | None) -> str | None:
    if cred is None:
        return None
    raw = getattr(cred, "profile_id", None)
    return raw.strip() if isinstance(raw, str) and raw.strip() else None


def merge_display_name_into_tags(
    tags: dict[str, Any] | None,
    display_name: str | None,
) -> dict[str, Any] | None:
    """将顶层 display_name 并入 tags（创建/更新 Gateway 模型共用）。"""
    if display_name is None:
        return tags
    trimmed = str(display_name).strip()
    if not trimmed:
        return tags
    merged = dict(tags or {})
    merged["display_name"] = trimmed
    return merged


def _prepare_gateway_model_write_fields(
    *,
    provider: str,
    real_model: str,
    tags: dict[str, Any] | None,
    credential_provider: str,
    upstream_profile_id: str | None = None,
    credential_api_base: str | None = None,
) -> _PreparedGatewayModelWrite:
    raw_rm = str(real_model).strip()
    if not raw_rm:
        raise ValidationError("上游模型 ID 不能为空")
    prov_norm = provider.strip().lower()
    if credential_provider.strip().lower() != prov_norm:
        raise ValidationError(
            f"凭据提供商为 {credential_provider}，与请求的 provider {provider} 不一致"
        )
    normalized_rm = normalize_gateway_stored_real_model(
        prov_norm,
        raw_rm,
        api_base=credential_api_base,
    )
    prefix_msg = litellm_prefix_violation_message(provider, normalized_rm)
    if prefix_msg:
        raise ValidationError(prefix_msg)
    working_tags = dict(tags or {})
    catalog_capability: str | None = None
    if should_apply_catalog_prep_to_base_tags(working_tags):
        catalog_capability, working_tags = prepare_gateway_write_from_upstream_catalog(
            provider=prov_norm,
            upstream_id=raw_rm,
            owned_by=None,
            api_base=credential_api_base,
            base_tags=working_tags,
            capability_override=None,
        )
    enriched_tags = build_gateway_model_tags(
        working_tags,
        provider=provider,
        real_model=normalized_rm,
        upstream_profile_id=upstream_profile_id,
        skip_hints=is_config_managed_system_gateway_model(tags=tags),
    )
    return _PreparedGatewayModelWrite(
        normalized_real_model=normalized_rm,
        enriched_tags=enriched_tags,
        catalog_capability=catalog_capability,
    )


def _normalize_real_model_for_update(
    provider: str,
    raw_model_id: str,
    credential: object | None,
    *,
    validate_prefix: bool = False,
) -> str:
    raw = str(raw_model_id).strip()
    if not raw:
        raise ValidationError("上游模型 ID 不能为空")
    normalized = normalize_stored_real_model_for_credential(provider, raw, credential)
    if validate_prefix:
        prefix_msg = litellm_prefix_violation_message(provider, normalized)
        if prefix_msg:
            raise ValidationError(prefix_msg)
    return normalized


class ModelWritesMixin:
    """写侧 mixin — 由 GatewayManagementWriteService 组合。"""

    async def _assert_model_name_free_of_route_grant_alias(
        self, tenant_id: uuid.UUID | None, name: str
    ) -> None:
        if tenant_id is None:
            return
        from domains.gateway.domain.policies.route_grant_access import (
            assert_local_name_free_of_grant_alias,
        )

        assert_local_name_free_of_grant_alias(
            name,
            grant_alias_in_use=(
                await self._route_grants.get_active_alias(tenant_id, name) is not None
            ),
            kind="model",
        )

    async def _resync_model_tags_pipeline(
        self,
        *,
        existing: Any,
        merged_tags: dict[str, Any],
        real_for_tags: str,
        cred_for_tags: object | None,
        config_managed: bool,
        owner_tenant_id: uuid.UUID | None,
        model_name: str,
    ) -> _ResyncTagsPrepResult:
        stripped = strip_litellm_capability_tags(dict(merged_tags))
        api_base = credential_api_base(cred_for_tags)
        inferred_cap, pre_tags = prepare_gateway_write_from_upstream_catalog(
            provider=existing.provider,
            upstream_id=real_for_tags,
            owned_by=None,
            api_base=api_base,
            base_tags=stripped,
            capability_override=None,
        )
        enriched = build_gateway_model_tags(
            pre_tags,
            provider=existing.provider,
            real_model=real_for_tags,
            upstream_profile_id=_upstream_profile_id_from_credential(cred_for_tags),
            skip_hints=config_managed,
            hint_mode="resync",
        )
        cap_update: str | None = None
        existing_cap = str(existing.capability or "").strip()
        if inferred_cap is not None and inferred_cap != existing_cap:
            if owner_tenant_id is not None:
                try:
                    await self._assert_capability_compatible_with_routes(
                        tenant_id=owner_tenant_id,
                        model_name=model_name,
                        new_capability=inferred_cap,
                    )
                    cap_update = inferred_cap
                except ValidationError:
                    logger.warning(
                        "resync capability %r skipped for model %s (route conflict); "
                        "tags updated only",
                        inferred_cap,
                        model_name,
                    )
            else:
                cap_update = inferred_cap
        return _ResyncTagsPrepResult(tags=enriched, capability=cap_update)

    async def _assert_capability_compatible_with_routes(
        self,
        *,
        tenant_id: uuid.UUID,
        model_name: str,
        new_capability: str,
    ) -> None:
        routes = await self._routes.list_for_tenant(tenant_id, only_enabled=False)
        new_cap = new_capability.strip().lower()
        for route in routes:
            primary = list(route.primary_models or ())
            if model_name not in primary:
                continue
            for sibling_name in primary:
                if sibling_name == model_name:
                    continue
                sibling = await self._models.get_by_name(tenant_id, sibling_name)
                if sibling is None:
                    continue
                sibling_cap = str(sibling.capability or "").strip().lower()
                if sibling_cap != new_cap:
                    virtual = getattr(route, "virtual_model", route)
                    raise ValidationError(
                        f"虚拟路由 {virtual!r} 内各 deployment 的 capability 须一致；"
                        f"{sibling_name!r} 为 {sibling_cap!r}，无法将当前模型改为 {new_cap!r}"
                    )

    async def _assert_team_model_mutation_allowed(
        self,
        *,
        credential_id: uuid.UUID,
        tenant_id: uuid.UUID,
        actor_user_id: uuid.UUID | None,
        team_role: str,
        is_platform_admin: bool,
        mutation: str,
        model_created_by_user_id: uuid.UUID | None = None,
    ) -> None:
        from domains.gateway.domain.policies.team_model_access import (
            actor_created_model,
            assert_can_create_model_on_team_credential,
            assert_can_delete_team_model_on_credential,
            assert_can_update_team_model_on_credential,
        )

        # 模型创建者对自己创建的模型拥有 update/delete 权限（无需检查凭据归属）
        if (
            mutation in ("update", "delete")
            and actor_user_id is not None
            and actor_created_model(
                model_created_by_user_id=model_created_by_user_id,
                actor_user_id=actor_user_id,
            )
        ):
            return

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

    async def create_personal_models(
        self,
        user_id: uuid.UUID,
        *,
        display_name: str,
        provider: str,
        model_id: str,
        credential_id: uuid.UUID,
        model_types: list[str],
        tags: dict[str, Any] | None = None,
        enabled: bool = True,
        reload_router: bool = True,
    ) -> list[Any]:
        from domains.gateway.application.personal_models import (
            capability_for_model_type,
            personal_model_alias,
            tags_for_model_type,
        )

        if provider not in PERSONAL_MODEL_PROVIDERS:
            raise ValidationError(f"不支持的提供商: {provider}")
        if not model_types:
            raise ValidationError("model_types 不能为空")
        invalid = set(model_types) - PERSONAL_MODEL_TYPES
        if invalid:
            raise ValidationError(f"无效的模型类型: {sorted(invalid)}")
        await self._assert_user_owns_credential(user_id, credential_id)
        cred_row = await self._creds.get(credential_id)
        if cred_row is None:
            raise CredentialNotFoundError(str(credential_id))
        if cred_row.provider.strip().lower() != provider.strip().lower():
            raise ValidationError(
                f"凭据提供商为 {cred_row.provider}，与所选 provider {provider} 不一致"
            )
        tenant_id = await self._ensure_personal_tenant_id(user_id)
        real_model = normalize_stored_real_model_for_credential(
            provider,
            str(model_id).strip(),
            cred_row,
        )
        created: list[Any] = []
        for idx, mtype in enumerate(model_types):
            cap = capability_for_model_type(mtype)
            alias = personal_model_alias(display_name, mtype, suffix=idx if idx else 0)
            suffix = 0
            while await self._models.name_exists_for_tenant(tenant_id, alias):
                suffix += 1
                alias = personal_model_alias(display_name, mtype, suffix=suffix)
            mtags = tags_for_model_type(mtype)
            mtags["display_name"] = display_name
            if tags:
                mtags.update({k: v for k, v in tags.items() if v is not None})
            mtags = build_gateway_model_tags(
                mtags,
                provider=provider,
                real_model=real_model,
                upstream_profile_id=_upstream_profile_id_from_credential(cred_row),
            )
            row = await self._models.create(
                tenant_id=tenant_id,
                name=alias,
                capability=cap,
                real_model=real_model,
                credential_id=credential_id,
                provider=provider,
                weight=1,
                rpm_limit=None,
                tpm_limit=None,
                tags=mtags,
                enabled=enabled,
                created_by_user_id=user_id,
            )
            created.append(row)
        if reload_router:
            await self.reload_litellm_router(tenant_id=tenant_id)
        return created

    async def update_personal_model(
        self, user_id: uuid.UUID, model_id: uuid.UUID, fields: dict[str, Any]
    ) -> Any:
        from domains.gateway.application.personal_models import capability_for_model_type

        tenant_id = await self._ensure_personal_tenant_id(user_id)
        existing = await self._models.get_for_tenant(model_id, tenant_id)
        if existing is None:
            raise ManagementEntityNotFoundError("model", str(model_id))
        incoming = dict(fields)
        resync_capabilities = bool(incoming.pop("resync_capabilities", False))
        model_types_raw = incoming.pop("model_types", None)
        new_name_raw = incoming.pop("name", None)
        if resync_capabilities and is_config_managed_system_gateway_model(tags=existing.tags):
            raise ValidationError("配置托管的系统模型不可从 LiteLLM 同步能力")

        update_fields: dict[str, Any] = {}
        if new_name_raw is not None:
            new_name = str(new_name_raw).strip()
            if not new_name:
                raise ValidationError("调用名称不能为空")
            if new_name != existing.name:
                if await self._models.name_exists_in_scope(tenant_id, new_name, exclude_id=model_id):
                    raise ValidationError(f"调用名称已存在: {new_name}")
                await self._assert_model_name_free_of_route_grant_alias(tenant_id, new_name)
                await rename_gateway_model_name_references(
                    self._session,
                    tenant_id=tenant_id,
                    old_name=existing.name,
                    new_name=new_name,
                )
                update_fields["name"] = new_name
            # 如果 new_name 与 existing.name 相同，无需加入 update_fields，避免无意义的 UPDATE 与 router reload
        if "credential_id" in incoming and incoming["credential_id"] is not None:
            await self._assert_user_owns_credential(user_id, incoming["credential_id"])
            nrow = await self._creds.get(incoming["credential_id"])
            if nrow is None:
                raise CredentialNotFoundError(str(incoming["credential_id"]))
            if nrow.provider.strip().lower() != existing.provider.strip().lower():
                raise ValidationError(
                    f"凭据提供商为 {nrow.provider}，与当前模型的 provider（{existing.provider}）不一致"
                )
            update_fields["credential_id"] = incoming["credential_id"]
        if incoming.get("model_id") is not None:
            cred_for_rm = None
            if incoming.get("credential_id") is not None:
                cred_for_rm = await self._creds.get(incoming["credential_id"])
            if cred_for_rm is None:
                cred_for_rm = await self._creds.get(existing.credential_id)
            update_fields["real_model"] = _normalize_real_model_for_update(
                existing.provider,
                str(incoming["model_id"]),
                cred_for_rm,
            )
        if incoming.get("is_active") is not None:
            update_fields["enabled"] = incoming["is_active"]
        if incoming.get("weight") is not None:
            update_fields["weight"] = assert_deployment_weight(incoming["weight"])
        if model_types_raw is not None:
            if not model_types_raw:
                raise ValidationError("model_types 不能为空")
            normalized_types = [str(t).strip().lower() for t in model_types_raw]
            invalid = set(normalized_types) - PERSONAL_MODEL_TYPES
            if invalid:
                raise ValidationError(f"无效的模型类型: {sorted(invalid)}")
            primary_cap = capability_for_model_type(normalized_types[0])
            update_fields["capability"] = primary_cap
            validate_model_types_for_capability(normalized_types, primary_cap)
        if incoming.get("display_name") is not None:
            merged_tags = dict(existing.tags or {})
            merged_tags["display_name"] = incoming["display_name"]
            update_fields["tags"] = merged_tags

        config_managed = is_config_managed_system_gateway_model(tags=existing.tags)
        needs_tags_pipeline = (
            resync_capabilities
            or model_types_raw is not None
            or "real_model" in update_fields
            or "tags" in update_fields
            or "credential_id" in update_fields
        )
        if needs_tags_pipeline:
            merged_tags = dict(existing.tags or {})
            if isinstance(update_fields.get("tags"), dict):
                merged_tags.update(update_fields["tags"])
            effective_capability = str(
                update_fields.get("capability") or existing.capability
            ).strip()
            if model_types_raw is not None:
                normalized_types = [str(t).strip().lower() for t in model_types_raw]
                merged_tags = tags_from_model_types(
                    normalized_types,
                    existing_tags=merged_tags,
                    capability=effective_capability,
                )
            real_for_tags = str(update_fields.get("real_model") or existing.real_model).strip()
            effective_cred_id = update_fields.get("credential_id") or existing.credential_id
            cred_for_tags = None
            if effective_cred_id is not None:
                cred_for_tags = await self._creds.get(effective_cred_id)
            if resync_capabilities:
                resync_result = await self._resync_model_tags_pipeline(
                    existing=existing,
                    merged_tags=merged_tags,
                    real_for_tags=real_for_tags,
                    cred_for_tags=cred_for_tags,
                    config_managed=config_managed,
                    owner_tenant_id=tenant_id,
                    model_name=existing.name,
                )
                update_fields["tags"] = resync_result.tags
                if resync_result.capability is not None:
                    update_fields["capability"] = resync_result.capability
            else:
                update_fields["tags"] = build_gateway_model_tags(
                    merged_tags,
                    provider=existing.provider,
                    real_model=real_for_tags,
                    upstream_profile_id=_upstream_profile_id_from_credential(cred_for_tags),
                    skip_hints=config_managed,
                    hint_mode="fill_missing",
                )

        if not update_fields:
            return existing
        updated = await self._models.update(model_id, **update_fields)
        if updated is None:
            raise ManagementEntityNotFoundError("model", str(model_id))
        await self.reload_litellm_router(tenant_id=tenant_id)
        return updated

    async def delete_personal_model(self, user_id: uuid.UUID, model_id: uuid.UUID) -> None:
        tenant_id = await self._ensure_personal_tenant_id(user_id)
        existing = await self._models.get_for_tenant(model_id, tenant_id)
        if existing is None:
            raise ManagementEntityNotFoundError("model", str(model_id))
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

    async def resync_personal_models_capabilities_batch(
        self,
        user_id: uuid.UUID,
        model_ids: list[uuid.UUID],
    ) -> GatewayModelBatchResyncCapabilitiesResult:
        tenant_id = await self._ensure_personal_tenant_id(user_id)
        return await self.resync_gateway_models_capabilities_batch(
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
                "系统凭据注册的模型应写入 system_gateway_models；"
                "请使用 create_system_gateway_model 或系统凭据批量导入"
            )
        from domains.gateway.domain.policies.route_grant_access import (
            assert_local_name_free_of_grant_alias,
        )

        assert_local_name_free_of_grant_alias(
            name,
            grant_alias_in_use=(
                await self._route_grants.get_active_alias(tenant_id, name) is not None
            ),
            kind="model",
        )
        prepared = _prepare_gateway_model_write_fields(
            provider=provider,
            real_model=real_model,
            tags=tags,
            credential_provider=cred.provider,
            upstream_profile_id=_upstream_profile_id_from_credential(cred),
            credential_api_base=credential_api_base(cred),
        )
        row = await self._models.create(
            tenant_id=tenant_id,
            name=name,
            capability=prepared.catalog_capability or capability,
            real_model=prepared.normalized_real_model,
            credential_id=credential_id,
            provider=provider,
            weight=weight,
            rpm_limit=rpm_limit,
            tpm_limit=tpm_limit,
            tags=prepared.enriched_tags,
            upstream_call_shape=upstream_call_shape,
            enabled=enabled,
            created_by_user_id=actor_user_id,
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
            upstream_profile_id=_upstream_profile_id_from_credential(cred),
            credential_api_base=credential_api_base(cred),
        )
        row = await self._models.create_system(
            name=name,
            capability=prepared.catalog_capability or capability,
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

    async def append_credential_to_existing_model_name(
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
        upstream_call_shape: str | None,
        actor_user_id: uuid.UUID | None,
        team_role: str,
        is_platform_admin: bool,
        enabled: bool = True,
    ) -> Any:
        """注册别名已存在时，自动将其转化为（或追加到）多凭据路由。

        返回新创建的 GatewayModel（--hash 别名）。
        """
        cleaned_name = (name or "").strip()
        if not cleaned_name:
            raise ValidationError("注册别名不能为空")

        # real_model 存储上游模型 ID，不加 LiteLLM provider 前缀
        real_model = str(real_model).strip()

        existing = await self._models.get_by_name(tenant_id, cleaned_name)
        route = await self._routes.get_by_virtual_model(tenant_id, cleaned_name)

        if existing is not None:
            if str(existing.credential_id) == str(credential_id):
                raise ValidationError(f"注册别名已存在: {cleaned_name}")
            if existing.real_model != real_model:
                raise ValidationError(
                    f"现有模型 {cleaned_name} 的上游模型 ID 为 {existing.real_model}，"
                    f"与新请求的 {real_model} 不一致；"
                    f"多凭据路由要求同一 (provider, real_model)"
                )
        elif route is None:
            raise ValidationError(f"模型 {cleaned_name} 不存在")

        # 生成新模型的 hash 别名
        short = uuid.UUID(str(credential_id)).hex[:8]
        new_alias = f"{cleaned_name}--{short}"
        suffix = 0
        base_alias = new_alias
        while await self._models.name_exists_for_tenant(tenant_id, new_alias):
            suffix += 1
            new_alias = f"{base_alias}-{suffix}"

        # 创建新模型
        new_model = await self.create_gateway_model(
            tenant_id=tenant_id,
            name=new_alias,
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
            reload_router=False,
        )

        if route is not None:
            # 追加到已有 route
            primary = list(route.primary_models or ())
            if new_alias not in primary:
                primary.append(new_alias)
                await self._routes.update(route.id, primary_models=primary)
        else:
            # 没有 route：将现有模型重命名并创建 route
            existing_short = uuid.UUID(str(existing.credential_id)).hex[:8]
            existing_alias = f"{cleaned_name}--{existing_short}"
            suffix = 0
            base_existing_alias = existing_alias
            while await self._models.name_exists_for_tenant(tenant_id, existing_alias):
                suffix += 1
                existing_alias = f"{base_existing_alias}-{suffix}"

            await rename_gateway_model_name_references(
                self._session,
                tenant_id=tenant_id,
                old_name=existing.name,
                new_name=existing_alias,
            )
            await self._models.update(existing.id, name=existing_alias)

            await self._routes.create(
                tenant_id=tenant_id,
                virtual_model=cleaned_name,
                primary_models=[existing_alias, new_alias],
                strategy="simple-shuffle",
            )

        await self.reload_litellm_router(tenant_id=tenant_id)
        return new_model

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
        strategy: str = "simple-shuffle",
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
        cleaned_name = (name or "").strip()
        if not cleaned_name:
            raise ValidationError("虚拟模型名不能为空")
        if not credential_ids:
            raise ValidationError("credential_ids 不能为空")
        if len(set(credential_ids)) != len(credential_ids):
            raise ValidationError("credential_ids 不能包含重复项")
        strategy_norm = validate_routing_strategy(strategy)
        repo = self._models
        if await repo.name_exists_for_tenant(tenant_id, cleaned_name):
            raise ValidationError(f"虚拟模型名 {cleaned_name} 与现有 GatewayModel 别名冲突")
        existing_route = await self._routes.get_by_virtual_model(tenant_id, cleaned_name)
        if existing_route is not None:
            raise ValidationError(f"虚拟模型名 {cleaned_name} 已存在 GatewayRoute")
        for cid in credential_ids:
            bindable = await self._creds.get_bindable_for_team_gateway_model(
                cid, tenant_id=tenant_id, is_platform_admin=is_platform_admin
            )
            if bindable is None:
                raise CredentialNotFoundError(str(cid))
            if not team_model_credential_scope_allowed(bindable_credential_scope(bindable)):
                raise ValidationError("多凭据注册不支持系统凭据；请使用系统模型单独注册或批量导入")
        from domains.gateway.infrastructure.models.gateway_model import GatewayModel

        created_models: list[GatewayModel] = []
        route = None
        try:
            for cid in credential_ids:
                short = uuid.UUID(str(cid)).hex[:8]
                alias = f"{cleaned_name}--{short}"
                suffix = 0
                base_alias = alias
                while await repo.name_exists_for_tenant(tenant_id, alias):
                    suffix += 1
                    alias = f"{base_alias}-{suffix}"
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
            route = await self._routes.create(
                tenant_id=tenant_id,
                virtual_model=cleaned_name,
                primary_models=[m.name for m in created_models],
                strategy=strategy_norm,
            )
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
        display_name_raw = update_fields.pop("display_name", None)
        if display_name_raw is not None:
            trimmed_display = str(display_name_raw).strip()
            if not trimmed_display:
                raise ValidationError("显示名不能为空")
            merged_tags = dict(existing.tags or {})
            if isinstance(update_fields.get("tags"), dict):
                merged_tags.update(update_fields["tags"])
            merged_tags["display_name"] = trimmed_display
            update_fields["tags"] = merged_tags
        if "credential_id" in update_fields and update_fields["credential_id"] is not None:
            new_cid_raw = update_fields["credential_id"]
            new_cid = (
                new_cid_raw if isinstance(new_cid_raw, uuid.UUID) else uuid.UUID(str(new_cid_raw))
            )
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
                raise ValidationError("团队模型不可绑定系统凭据")
            if cred.provider.strip().lower() != existing.provider.strip().lower():
                raise ValidationError(
                    f"凭据提供商为 {cred.provider}，与当前模型的 provider（{existing.provider}）不一致"
                )
        if "real_model" in update_fields and update_fields["real_model"] is not None:
            effective_cred_id = update_fields.get("credential_id") or existing.credential_id
            cred_for_rm: object | None = None
            if effective_cred_id is not None:
                if owner_tenant_id is None:
                    cred_for_rm = await self._system_creds.get(effective_cred_id)
                else:
                    cred_for_rm = await self._creds.get_bindable_for_team_gateway_model(
                        effective_cred_id,
                        tenant_id=tenant_id,
                        is_platform_admin=is_platform_admin,
                    )
            update_fields["real_model"] = _normalize_real_model_for_update(
                existing.provider,
                str(update_fields["real_model"]),
                cred_for_rm,
                validate_prefix=True,
            )
        if "weight" in update_fields and update_fields["weight"] is not None:
            update_fields["weight"] = assert_deployment_weight(update_fields["weight"])
        if "upstream_call_shape" in update_fields:
            shape_raw = update_fields["upstream_call_shape"]
            if shape_raw is None or (isinstance(shape_raw, str) and not shape_raw.strip()):
                update_fields["upstream_call_shape"] = None
            else:
                shape = str(shape_raw).strip().lower()
                if shape not in _ALLOWED_UPSTREAM_CALL_SHAPES:
                    raise ValidationError(
                        f"upstream_call_shape 须为 {sorted(_ALLOWED_UPSTREAM_CALL_SHAPES)} 之一"
                    )
                update_fields["upstream_call_shape"] = shape
        config_managed = is_config_managed_system_gateway_model(tags=existing.tags)
        model_types_raw = update_fields.pop("model_types", None)
        if "capability" in update_fields and update_fields["capability"] is not None:
            new_capability = _parse_gateway_capability(str(update_fields["capability"]))
            if config_managed:
                raise ValidationError("配置托管的系统模型不可修改主调用面")
            existing_cap = str(existing.capability or "").strip().lower()
            if new_capability != existing_cap and owner_tenant_id is not None:
                await self._assert_capability_compatible_with_routes(
                    tenant_id=owner_tenant_id,
                    model_name=existing.name,
                    new_capability=new_capability,
                )
            update_fields["capability"] = new_capability
        resync_capabilities = bool(update_fields.pop("resync_capabilities", False))
        if resync_capabilities and config_managed:
            raise ValidationError("配置托管的系统模型不可从 LiteLLM 同步能力")
        effective_capability = str(
            update_fields.get("capability") or existing.capability
        ).strip()
        if model_types_raw is not None:
            if config_managed:
                raise ValidationError("配置托管的系统模型不可修改产品特性")
            validate_model_types_for_capability(model_types_raw, effective_capability)
        needs_tags_pipeline = (
            resync_capabilities
            or "real_model" in update_fields
            or "tags" in update_fields
            or model_types_raw is not None
            or "capability" in update_fields
            or "credential_id" in update_fields
        )
        if needs_tags_pipeline:
            merged_tags = dict(existing.tags or {})
            if isinstance(update_fields.get("tags"), dict):
                merged_tags.update(update_fields["tags"])
            if model_types_raw is not None:
                merged_tags = tags_from_model_types(
                    model_types_raw,
                    existing_tags=merged_tags,
                    capability=effective_capability,
                )
            real_for_tags = str(update_fields.get("real_model") or existing.real_model).strip()
            effective_cred_id = update_fields.get("credential_id") or existing.credential_id
            cred_for_tags: object | None = None
            if effective_cred_id is not None:
                if owner_tenant_id is None:
                    cred_for_tags = await self._system_creds.get(effective_cred_id)
                else:
                    cred_for_tags = await self._creds.get_bindable_for_team_gateway_model(
                        effective_cred_id,
                        tenant_id=tenant_id,
                        is_platform_admin=is_platform_admin,
                    )
            if resync_capabilities:
                resync_result = await self._resync_model_tags_pipeline(
                    existing=existing,
                    merged_tags=merged_tags,
                    real_for_tags=real_for_tags,
                    cred_for_tags=cred_for_tags,
                    config_managed=config_managed,
                    owner_tenant_id=owner_tenant_id,
                    model_name=existing.name,
                )
                update_fields["tags"] = resync_result.tags
                if resync_result.capability is not None:
                    update_fields["capability"] = resync_result.capability
            else:
                update_fields["tags"] = build_gateway_model_tags(
                    merged_tags,
                    provider=existing.provider,
                    real_model=real_for_tags,
                    upstream_profile_id=_upstream_profile_id_from_credential(cred_for_tags),
                    skip_hints=config_managed,
                    hint_mode="fill_missing",
                )
        new_name_raw = update_fields.get("name")
        if new_name_raw is not None:
            new_name = str(new_name_raw).strip()
            if not new_name:
                raise ValidationError("注册别名不能为空")
            update_fields["name"] = new_name
            if new_name != existing.name:
                if block_config_managed_rename:
                    raise ValidationError("配置托管的系统模型不可修改注册别名")
                if await repo.name_exists_in_scope(owner_tenant_id, new_name, exclude_id=model_id):
                    raise ValidationError(f"注册别名已存在: {new_name}")
                await self._assert_model_name_free_of_route_grant_alias(owner_tenant_id, new_name)
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
                raise ManagementEntityNotFoundError("model", str(model_id))
            await self._assert_team_model_mutation_allowed(
                credential_id=existing.credential_id,
                tenant_id=tenant_id,
                actor_user_id=actor_user_id,
                team_role=team_role,
                is_platform_admin=is_platform_admin,
                mutation="update",
                model_created_by_user_id=existing.created_by_user_id,
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
                raise ManagementEntityNotFoundError("model", str(model_id))
            if reload_router:
                await self.reload_litellm_router(tenant_id=tenant_id)
            return updated

        system_existing = await repo.get_system(model_id)
        if system_existing is None:
            raise ManagementEntityNotFoundError("model", str(model_id))

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
            raise ManagementEntityNotFoundError("model", str(model_id))
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
                raise ManagementEntityNotFoundError("model", str(model_id))
            await self._assert_team_model_mutation_allowed(
                credential_id=existing.credential_id,
                tenant_id=tenant_id,
                actor_user_id=actor_user_id,
                team_role=team_role,
                is_platform_admin=is_platform_admin,
                mutation="delete",
                model_created_by_user_id=existing.created_by_user_id,
            )
            model_name = existing.name
            await repo.delete(model_id)
            return model_id, model_name

        system_existing = await repo.get_system(model_id)
        if system_existing is None:
            raise ManagementEntityNotFoundError("model", str(model_id))

        from domains.gateway.domain.policies.credential_scope import (
            assert_system_credential_mutation_allowed,
        )
        from domains.gateway.domain.types import is_config_managed_system_gateway_model

        assert_system_credential_mutation_allowed(is_platform_admin=is_platform_admin)
        if is_config_managed_system_gateway_model(tags=system_existing.tags):
            raise ValidationError(
                "配置同步托管的系统模型不可删除；请通过 gateway-catalog 或配置管理"
            )
        model_name = system_existing.name
        await repo.delete_system(model_id)
        return model_id, model_name

    @staticmethod
    def _batch_operation_failure(
        model_id: uuid.UUID,
        exc: BaseException,
    ) -> GatewayModelBatchOperationFailure:
        code = getattr(exc, "code", None) or exc.__class__.__name__
        message = getattr(exc, "message", None) or str(exc)
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
        if deleted_ids:
            from domains.gateway.application.resource_grant_cleanup import (
                purge_resource_grants_for_subjects,
            )

            await purge_resource_grants_for_subjects(
                self._session,
                subjects=[("model", list(deleted_ids))],
            )
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
                f"单次最多删除 {_BATCH_MODEL_OP_MAX} 个模型",
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
                f"单次最多同步 {_BATCH_MODEL_OP_MAX} 个模型能力",
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
                    fields={"resync_capabilities": True},
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

    async def _rollback_ephemeral_model_copy_credential(
        self,
        *,
        ephemeral_dest_cred_id: uuid.UUID | None,
        group_rows: list[Any],
        succeeded: list[Any],
        dest_cred_cache: dict[uuid.UUID, uuid.UUID],
        source_cred_id: uuid.UUID,
    ) -> None:
        """``copy_credential`` 组内无模型成功时删除刚创建的孤儿凭据。"""
        if ephemeral_dest_cred_id is None:
            return
        group_had_success = any(
            any(s.source_model_id == str(row.id) for s in succeeded) for row in group_rows
        )
        if group_had_success:
            return
        with suppress(Exception):
            await self._creds.delete(ephemeral_dest_cred_id)
        dest_cred_cache.pop(source_cred_id, None)

    async def copy_models_to_team(
        self,
        *,
        model_ids: list[uuid.UUID],
        destination_team_id: uuid.UUID,
        credential_plans: list[ModelCopyCredentialPlan],
        actor_user_id: uuid.UUID,
        is_platform_admin: bool,
        destination_team_role: str,
        platform_user_role: str,
    ):
        """Copy a subset of gateway_models rows to another team."""
        from domains.gateway.application.management.model_copy_types import (
            CopyModelsToTeamResult,
            ModelCopyFailure,
            ModelCopySuccess,
        )
        from domains.gateway.domain.policies.credential_copy_policy import (
            CredentialCopyScope,
            assert_credential_copy_destination_allowed,
            assert_credential_copy_source_allowed,
        )
        from domains.gateway.domain.policies.model_copy_policy import (
            assert_model_copy_credential_plan_valid,
            assert_model_copy_destination_credential_allowed,
            assert_model_copy_destination_differs,
            assert_model_copy_source_credential_allowed,
            model_copy_failure_reason,
        )

        if len(model_ids) > _BATCH_MODEL_OP_MAX:
            raise ValidationError(
                f"单次最多复制 {_BATCH_MODEL_OP_MAX} 个模型",
            )
        if not model_ids:
            raise ValidationError("model_ids must not be empty")

        assert_credential_copy_destination_allowed(
            destination=CredentialCopyScope(kind="team", team_id=destination_team_id),
            destination_team_role=destination_team_role,
            is_platform_admin=is_platform_admin,
        )

        personal_team_id = await self._ensure_personal_tenant_id(actor_user_id)
        plan_by_cred: dict[uuid.UUID, ModelCopyCredentialPlan] = {
            plan.source_credential_id: plan for plan in credential_plans
        }
        if len(plan_by_cred) != len(credential_plans):
            raise ValidationError(
                "credential_plans must have unique source_credential_id values"
            )
        for plan in credential_plans:
            assert_model_copy_credential_plan_valid(
                mode=plan.mode,
                destination_credential_id=plan.destination_credential_id,
            )

        unique_ids = list(dict.fromkeys(model_ids))
        models_by_id: dict[uuid.UUID, Any] = {}
        for model_id in unique_ids:
            row = await self._models.get(model_id)
            if row is not None:
                models_by_id[model_id] = row

        from domains.tenancy.application.management_team_resolve_use_case import (
            TenancyManagementTeamResolveUseCase,
        )

        team_resolver = TenancyManagementTeamResolveUseCase(self._session)
        source_team_roles: dict[uuid.UUID, str] = {}
        for tenant_id in {
            row.tenant_id
            for row in models_by_id.values()
            if row.tenant_id != personal_team_id
        }:
            ctx = await team_resolver.resolve_management_team(
                user_id=actor_user_id,
                platform_user_role=platform_user_role,
                x_team_id=None,
                path_team_id=str(tenant_id),
            )
            source_team_roles[tenant_id] = ctx.team_role

        groups: dict[uuid.UUID, list[Any]] = {}
        succeeded: list[ModelCopySuccess] = []
        failed: list[ModelCopyFailure] = []

        for model_id in unique_ids:
            row = models_by_id.get(model_id)
            if row is None:
                failed.append(
                    ModelCopyFailure(model_id=str(model_id), reason="model not found")
                )
                continue
            groups.setdefault(row.credential_id, []).append(row)

        dest_cred_cache: dict[uuid.UUID, uuid.UUID] = {}
        any_created = False

        for source_cred_id, group_rows in groups.items():
            plan = plan_by_cred.get(source_cred_id)
            if plan is None:
                for row in group_rows:
                    failed.append(
                        ModelCopyFailure(
                            model_id=str(row.id),
                            reason="credential plan not found",
                        )
                    )
                continue

            ephemeral_dest_cred_id: uuid.UUID | None = None
            try:
                source_cred = await self._creds.get(source_cred_id)
                if source_cred is None:
                    raise CredentialNotFoundError(str(source_cred_id))

                sample_tenant_id = group_rows[0].tenant_id
                source_team_role = (
                    None
                    if sample_tenant_id == personal_team_id
                    else source_team_roles.get(sample_tenant_id)
                )
                if sample_tenant_id != personal_team_id and source_team_role is None:
                    raise CredentialNotFoundError(str(source_cred_id))

                assert_model_copy_source_credential_allowed(
                    source_cred,
                    source_tenant_id=sample_tenant_id,
                    personal_team_id=personal_team_id,
                    actor_user_id=actor_user_id,
                    is_platform_admin=is_platform_admin,
                    source_team_role=source_team_role,
                    permission_denied_tenant_id=destination_team_id,
                )

                dest_cred_id = dest_cred_cache.get(source_cred_id)
                if dest_cred_id is None:
                    if plan.mode == "copy_credential":
                        source_scope = (
                            CredentialCopyScope(kind="personal")
                            if sample_tenant_id == personal_team_id
                            else CredentialCopyScope(
                                kind="team",
                                team_id=sample_tenant_id,
                            )
                        )
                        assert_credential_copy_source_allowed(
                            source_cred,
                            source=source_scope,
                            actor_user_id=actor_user_id,
                            is_platform_admin=is_platform_admin,
                            source_team_role=source_team_role,
                            permission_denied_tenant_id=destination_team_id,
                        )
                        target_name = await self._unique_copy_credential_name(
                            source_cred,
                            destination=CredentialCopyScope(
                                kind="team",
                                team_id=destination_team_id,
                            ),
                            actor_user_id=actor_user_id,
                        )
                        new_cred = await self._copy_credential_to_destination(
                            source_cred_id,
                            destination=CredentialCopyScope(
                                kind="team",
                                team_id=destination_team_id,
                            ),
                            actor_user_id=actor_user_id,
                            name_override=target_name,
                        )
                        if new_cred is None:
                            raise CredentialNotFoundError(str(source_cred_id))
                        dest_cred_id = new_cred.id
                        ephemeral_dest_cred_id = new_cred.id
                    else:
                        assert plan.destination_credential_id is not None
                        dest_cred = await self._creds.get(plan.destination_credential_id)
                        if dest_cred is None:
                            raise CredentialNotFoundError(str(plan.destination_credential_id))
                        assert_model_copy_destination_credential_allowed(
                            dest_cred,
                            destination_team_id=destination_team_id,
                            source_provider=str(group_rows[0].provider),
                            actor_user_id=actor_user_id,
                            destination_team_role=destination_team_role,
                            is_platform_admin=is_platform_admin,
                        )
                        dest_cred_id = dest_cred.id
                    dest_cred_cache[source_cred_id] = dest_cred_id

                for row in group_rows:
                    try:
                        assert_model_copy_destination_differs(
                            source_tenant_id=row.tenant_id,
                            destination_team_id=destination_team_id,
                        )
                        unique_name = await generate_unique_model_name(
                            lambda n, _tid=destination_team_id: self._models.name_exists_for_tenant(
                                _tid, n
                            ),
                            row.name,
                        )
                        created = await self._models.create(
                            tenant_id=destination_team_id,
                            name=unique_name,
                            capability=row.capability,
                            real_model=row.real_model,
                            credential_id=dest_cred_id,
                            provider=row.provider,
                            weight=row.weight or 1,
                            rpm_limit=row.rpm_limit,
                            tpm_limit=row.tpm_limit,
                            tags=row.tags,
                            upstream_call_shape=row.upstream_call_shape,
                            enabled=row.enabled,
                            created_by_user_id=actor_user_id,
                        )
                        succeeded.append(
                            ModelCopySuccess(
                                source_model_id=str(row.id),
                                new_model_id=str(created.id),
                                name=unique_name,
                            )
                        )
                        any_created = True
                    except Exception as exc:
                        failed.append(
                            ModelCopyFailure(
                                model_id=str(row.id),
                                reason=model_copy_failure_reason(exc),
                            )
                        )
                await self._rollback_ephemeral_model_copy_credential(
                    ephemeral_dest_cred_id=ephemeral_dest_cred_id,
                    group_rows=group_rows,
                    succeeded=succeeded,
                    dest_cred_cache=dest_cred_cache,
                    source_cred_id=source_cred_id,
                )
            except Exception as exc:
                await self._rollback_ephemeral_model_copy_credential(
                    ephemeral_dest_cred_id=ephemeral_dest_cred_id,
                    group_rows=group_rows,
                    succeeded=succeeded,
                    dest_cred_cache=dest_cred_cache,
                    source_cred_id=source_cred_id,
                )
                reason = model_copy_failure_reason(exc)
                for row in group_rows:
                    if not any(s.source_model_id == str(row.id) for s in succeeded):
                        failed.append(
                            ModelCopyFailure(model_id=str(row.id), reason=reason)
                        )

        if any_created:
            await self.reload_litellm_router(tenant_id=destination_team_id)

        return CopyModelsToTeamResult(succeeded=succeeded, failed=failed)
