"""Gateway 管理面变更应用服务（CQRS 写侧的工程分包；对外语义见架构文档术语表）。"""

from __future__ import annotations

from collections.abc import Iterable
from contextlib import suppress
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
import uuid

from bootstrap.config import settings as _settings
from domains.gateway.application.litellm_real_model_prefix import litellm_prefix_violation_message
from domains.gateway.application.management.model_test_constants import (
    GATEWAY_MODEL_TEST_SUPPORTED_CAPABILITIES,
)
from domains.gateway.application.management.multi_credential_types import (
    MultiCredentialGatewayModelResult,
)
from domains.gateway.application.model_reference_prune import (
    prune_gateway_model_name_references,
    rename_gateway_model_name_references,
)
from domains.gateway.application.routing_strategy_validation import validate_routing_strategy
from domains.gateway.domain.errors import (
    CredentialNameConflictError,
    CredentialNotFoundError,
    ManagementEntityNotFoundError,
    SystemCredentialAdminRequiredError,
    SystemVirtualKeyRevokeForbiddenError,
    TeamPermissionDeniedError,
    VirtualKeyNotFoundError,
)
from domains.gateway.domain.types import (
    CONFIG_MANAGED_BY,
    GATEWAY_MODEL_MANAGED_BY_TAG,
    PERSONAL_MODEL_PROVIDERS,
    PERSONAL_MODEL_TYPES,
    VirtualKeyBatchRevokeReason,
    is_config_managed_system_credential,
)
from domains.gateway.domain.virtual_key_access import assert_virtual_key_accessible_by_actor
from domains.gateway.infrastructure.models.entitlement_plan import EntitlementPlan
from domains.gateway.infrastructure.models.provider_plan import ProviderPlan
from domains.gateway.infrastructure.repositories.alert_repository import GatewayAlertRepository
from domains.gateway.infrastructure.repositories.budget_repository import BudgetRepository
from domains.gateway.infrastructure.repositories.credential_repository import (
    ProviderCredentialRepository,
)
from domains.gateway.infrastructure.repositories.entitlement_plan_repository import (
    EntitlementPlanRepository,
)
from domains.gateway.infrastructure.repositories.model_repository import (
    GatewayModelRepository,
    GatewayRouteRepository,
)
from domains.gateway.infrastructure.repositories.provider_plan_repository import (
    ProviderPlanRepository,
)
from domains.gateway.infrastructure.repositories.virtual_key_repository import (
    VirtualKeyRepository,
)
from domains.tenancy.application.team_service import TeamService
from libs.crypto import decrypt_value, derive_encryption_key
from libs.exceptions import ValidationError
from libs.llm.litellm_model_id import build_litellm_model_id
from libs.model_connectivity import truncate_last_test_reason
from utils.logging import get_logger

if TYPE_CHECKING:
    from decimal import Decimal

    from sqlalchemy.ext.asyncio import AsyncSession

    from domains.gateway.infrastructure.models.alert import GatewayAlertRule


logger = get_logger(__name__)


def _gateway_image_probe_size(provider: str) -> str:
    """生图探活用最小合法尺寸（各云厂商约束不同，与 Agent 侧 Seedream 默认对齐）。"""
    if provider == "volcengine":
        # 火山 Ark / Seedream 常用尺寸集，见 Agent image_generator 默认
        return "1920x1920"
    if provider == "openai":
        return "1024x1024"
    return "1024x1024"


async def _record_gateway_model_test_failure(
    models: GatewayModelRepository,
    model_id: uuid.UUID,
    tested_at: datetime,
    msg: str,
    litellm_model: str,
) -> dict[str, Any]:
    reason = truncate_last_test_reason(msg)
    await models.update(
        model_id,
        last_test_status="failed",
        last_tested_at=tested_at,
        last_test_reason=reason,
    )
    return {
        "success": False,
        "message": msg,
        "model": litellm_model,
        "status": "failed",
        "tested_at": tested_at,
        "reason": reason,
    }


async def _record_gateway_model_test_success(
    models: GatewayModelRepository,
    model_id: uuid.UUID,
    tested_at: datetime,
    litellm_model: str,
    *,
    response_preview: str | None = None,
) -> dict[str, Any]:
    await models.update(
        model_id,
        last_test_status="success",
        last_tested_at=tested_at,
        last_test_reason=None,
    )
    payload: dict[str, Any] = {
        "success": True,
        "message": "连接成功",
        "model": litellm_model,
        "status": "success",
        "tested_at": tested_at,
        "reason": None,
    }
    if response_preview is not None:
        payload["response_preview"] = response_preview
    return payload


def _image_generation_probe_preview(img_response: Any) -> str:
    preview = ""
    with suppress(Exception):
        data = getattr(img_response, "data", None)
        if data is None and isinstance(img_response, dict):
            raw = img_response.get("data")
            data = raw if isinstance(raw, list) else None
        if data and len(data) > 0:
            first = data[0]
            url: str | None
            b64: str | None
            if isinstance(first, dict):
                url = first.get("url") if isinstance(first.get("url"), str) else None
                b64 = first.get("b64_json") if isinstance(first.get("b64_json"), str) else None
            else:
                url = getattr(first, "url", None)
                b64 = getattr(first, "b64_json", None)
                url = url if isinstance(url, str) else None
                b64 = b64 if isinstance(b64, str) else None
            if url:
                preview = url[:100]
            elif b64:
                preview = f"{b64[:40]}…" if len(b64) > 40 else b64
    return preview


class GatewayManagementWriteService:
    """管理 API 状态变更，经仓储与领域服务落库"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._vkeys = VirtualKeyRepository(session)
        self._creds = ProviderCredentialRepository(session)
        self._models = GatewayModelRepository(session)
        self._routes = GatewayRouteRepository(session)
        self._budgets = BudgetRepository(session)
        self._alerts = GatewayAlertRepository(session)
        self._provider_plans = ProviderPlanRepository(session)
        self._entitlement_plans = EntitlementPlanRepository(session)
        self._teams = TeamService(session)

    async def _ensure_personal_team_id(self, user_id: uuid.UUID) -> uuid.UUID:
        personal_team = await self._teams.ensure_personal_team(user_id)
        return personal_team.id

    async def _assert_user_owns_credential(
        self, user_id: uuid.UUID, credential_id: uuid.UUID
    ) -> None:
        cred = await self._creds.get(credential_id)
        if cred is None or cred.scope != "user" or cred.scope_id != user_id:
            raise CredentialNotFoundError(str(credential_id))

    async def _cascade_delete_models_for_credential(self, credential_id: uuid.UUID) -> int:
        """删除引用该凭据的全部 gateway_models，并修剪 vkey / 路由中的模型名。"""
        models = await self._models.list_by_credential_id(credential_id)
        if not models:
            return 0
        model_names = frozenset(m.name for m in models)
        for model in models:
            await self._models.delete(model.id)
        await prune_gateway_model_name_references(self._session, model_names)
        return len(models)

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
        team_id = await self._ensure_personal_team_id(user_id)
        real_model = build_litellm_model_id(provider, model_id)
        created: list[Any] = []
        for idx, mtype in enumerate(model_types):
            cap = capability_for_model_type(mtype)
            alias = personal_model_alias(display_name, mtype, suffix=idx if idx else 0)
            suffix = 0
            while await self._models.name_exists_on_team(team_id, alias):
                suffix += 1
                alias = personal_model_alias(display_name, mtype, suffix=suffix)

            mtags = tags_for_model_type(mtype)
            mtags["display_name"] = display_name
            if tags:
                mtags.update({k: v for k, v in tags.items() if v is not None})

            row = await self._models.create(
                team_id=team_id,
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
            )
            created.append(row)

        if reload_router:
            await self.reload_litellm_router()
        return created

    async def update_personal_model(
        self,
        user_id: uuid.UUID,
        model_id: uuid.UUID,
        fields: dict[str, Any],
    ) -> Any:
        team_id = await self._ensure_personal_team_id(user_id)
        existing = await self._models.get_on_team(model_id, team_id)
        if existing is None:
            raise ManagementEntityNotFoundError("model", str(model_id))

        update_fields: dict[str, Any] = {}
        if "credential_id" in fields and fields["credential_id"] is not None:
            await self._assert_user_owns_credential(user_id, fields["credential_id"])
            nrow = await self._creds.get(fields["credential_id"])
            if nrow is None:
                raise CredentialNotFoundError(str(fields["credential_id"]))
            if nrow.provider.strip().lower() != existing.provider.strip().lower():
                raise ValidationError(
                    f"凭据提供商为 {nrow.provider}，与当前模型的 provider（{existing.provider}）不一致"
                )
            update_fields["credential_id"] = fields["credential_id"]
        if fields.get("model_id") is not None:
            update_fields["real_model"] = build_litellm_model_id(
                existing.provider, str(fields["model_id"])
            )
        if fields.get("is_active") is not None:
            update_fields["enabled"] = fields["is_active"]
        if fields.get("display_name") is not None:
            merged_tags = dict(existing.tags or {})
            merged_tags["display_name"] = fields["display_name"]
            update_fields["tags"] = merged_tags

        if not update_fields:
            return existing

        updated = await self._models.update(model_id, **update_fields)
        if updated is None:
            raise ManagementEntityNotFoundError("model", str(model_id))
        await self.reload_litellm_router()
        return updated

    async def delete_personal_model(self, user_id: uuid.UUID, model_id: uuid.UUID) -> None:
        team_id = await self._ensure_personal_team_id(user_id)
        existing = await self._models.get_on_team(model_id, team_id)
        if existing is None:
            raise ManagementEntityNotFoundError("model", str(model_id))
        model_name = existing.name
        await self._models.delete(model_id)
        await prune_gateway_model_name_references(self._session, frozenset({model_name}))
        await self.reload_litellm_router()

    async def test_personal_model(self, user_id: uuid.UUID, model_id: uuid.UUID) -> dict[str, Any]:
        team_id = await self._ensure_personal_team_id(user_id)
        return await self.test_gateway_model(model_id, team_id=team_id)

    async def create_virtual_key(
        self,
        *,
        team_id: uuid.UUID,
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
    ) -> Any:
        return await self._vkeys.create(
            team_id=team_id,
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

    async def revoke_virtual_key(
        self,
        key_id: uuid.UUID,
        *,
        team_id: uuid.UUID,
        actor_user_id: uuid.UUID | None,
        team_role: str,
        is_platform_admin: bool,
    ) -> None:
        record = await self._vkeys.get(key_id)
        assert_virtual_key_accessible_by_actor(
            record,
            key_id=str(key_id),
            team_id=team_id,
            actor_user_id=actor_user_id,
            team_role=team_role,
            is_platform_admin=is_platform_admin,
            require_active=False,
        )
        await self._vkeys.revoke(key_id)

    async def revoke_virtual_keys_batch(
        self,
        key_ids: list[uuid.UUID],
        *,
        team_id: uuid.UUID,
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
                    team_id=team_id,
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
        return revoked, failed

    async def create_team_credential(
        self,
        *,
        team_id: uuid.UUID,
        provider: str,
        name: str,
        api_key_encrypted: str,
        api_base: str | None,
        extra: dict[str, Any] | None,
    ) -> Any:
        row = await self._creds.create(
            scope="team",
            scope_id=team_id,
            provider=provider,
            name=name,
            api_key_encrypted=api_key_encrypted,
            api_base=api_base,
            extra=extra,
        )
        await self.reload_litellm_router()
        return row

    async def create_system_credential(
        self,
        *,
        is_platform_admin: bool,
        provider: str,
        name: str,
        api_key_encrypted: str,
        api_base: str | None,
        extra: dict[str, Any] | None,
    ) -> Any:
        if not is_platform_admin:
            raise SystemCredentialAdminRequiredError()
        row = await self._creds.create(
            scope="system",
            scope_id=None,
            provider=provider,
            name=name,
            api_key_encrypted=api_key_encrypted,
            api_base=api_base,
            extra=extra,
        )
        await self.reload_litellm_router()
        return row

    async def update_managed_credential(
        self,
        credential_id: uuid.UUID,
        *,
        team_id: uuid.UUID,
        is_platform_admin: bool,
        api_key_encrypted: str | None,
        api_base: str | None,
        extra: dict[str, Any] | None,
        is_active: bool | None,
        name: str | None,
    ) -> Any:
        existing = await self._creds.get(credential_id)
        if existing is None:
            raise CredentialNotFoundError(str(credential_id))
        if existing.scope == "system":
            if not is_platform_admin:
                raise SystemCredentialAdminRequiredError()
        elif existing.scope == "team":
            if existing.scope_id != team_id:
                raise CredentialNotFoundError(str(credential_id))
        else:
            raise CredentialNotFoundError(str(credential_id))
        if (
            name is not None
            and name != existing.name
            and is_config_managed_system_credential(
                scope=existing.scope,
                name=existing.name,
                extra=existing.extra,
            )
        ):
            raise ValidationError(
                "配置同步托管的系统凭据不可重命名；请通过环境变量或 app.toml 管理密钥",
            )
        updated = await self._creds.update(
            credential_id,
            api_key_encrypted=api_key_encrypted,
            api_base=api_base,
            extra=extra,
            is_active=is_active,
            name=name,
        )
        if updated is None:
            raise CredentialNotFoundError(str(credential_id))
        await self.reload_litellm_router()
        return updated

    async def delete_managed_credential(
        self,
        credential_id: uuid.UUID,
        *,
        team_id: uuid.UUID,
        is_platform_admin: bool,
    ) -> None:
        existing = await self._creds.get(credential_id)
        if existing is None:
            raise CredentialNotFoundError(str(credential_id))
        if existing.scope == "system":
            if not is_platform_admin:
                raise SystemCredentialAdminRequiredError()
        elif existing.scope == "team":
            if existing.scope_id != team_id:
                raise CredentialNotFoundError(str(credential_id))
        else:
            raise CredentialNotFoundError(str(credential_id))
        await self._cascade_delete_models_for_credential(credential_id)
        await self._creds.delete(credential_id)
        await self.reload_litellm_router()

    async def import_user_credential_to_team(
        self,
        *,
        user_credential_id: uuid.UUID,
        team_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        is_platform_admin: bool,
    ) -> Any:
        src = await self._creds.get(user_credential_id)
        if src is None or src.scope != "user":
            raise CredentialNotFoundError(str(user_credential_id))
        if src.scope_id != actor_user_id and not is_platform_admin:
            raise TeamPermissionDeniedError(str(team_id))
        new_cred = await self._creds.copy_to_team(user_credential_id, team_id)
        if new_cred is None:
            raise CredentialNotFoundError(str(user_credential_id))
        await self.reload_litellm_router()
        return new_cred

    async def import_all_user_credentials_to_team(
        self, *, actor_user_id: uuid.UUID, team_id: uuid.UUID
    ) -> int:
        user_creds = await self._creds.list_for_user(actor_user_id)
        created = 0
        for cred in user_creds:
            copied = await self._creds.copy_to_team(cred.id, team_id)
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
        extra: dict[str, Any] | None,
    ) -> Any:
        dup = await self._creds.find_user_by_provider_and_name(actor_user_id, provider, name)
        if dup is not None:
            raise CredentialNameConflictError(provider, name)
        row = await self._creds.create(
            scope="user",
            scope_id=actor_user_id,
            provider=provider,
            name=name,
            api_key_encrypted=api_key_encrypted,
            api_base=api_base,
            extra=extra,
        )
        await self.reload_litellm_router()
        return row

    async def update_user_credential(
        self,
        credential_id: uuid.UUID,
        *,
        actor_user_id: uuid.UUID,
        api_key_encrypted: str | None,
        api_base: str | None,
        extra: dict[str, Any] | None,
        is_active: bool | None,
        name: str | None,
    ) -> Any:
        existing = await self._creds.get(credential_id)
        if existing is None or existing.scope != "user" or existing.scope_id != actor_user_id:
            raise CredentialNotFoundError(str(credential_id))
        if name is not None and name != existing.name:
            dup = await self._creds.find_user_by_provider_and_name(
                actor_user_id, existing.provider, name
            )
            if dup is not None:
                raise CredentialNameConflictError(existing.provider, name)
        updated = await self._creds.update(
            credential_id,
            api_key_encrypted=api_key_encrypted,
            api_base=api_base,
            extra=extra,
            is_active=is_active,
            name=name,
        )
        if updated is None:
            raise CredentialNotFoundError(str(credential_id))
        await self.reload_litellm_router()
        return updated

    async def delete_user_credential(
        self, credential_id: uuid.UUID, *, actor_user_id: uuid.UUID, reload_router: bool = True
    ) -> None:
        existing = await self._creds.get(credential_id)
        if existing is None or existing.scope != "user" or existing.scope_id != actor_user_id:
            raise CredentialNotFoundError(str(credential_id))
        await self._cascade_delete_models_for_credential(credential_id)
        await self._creds.delete(credential_id)
        if reload_router:
            await self.reload_litellm_router()

    async def create_gateway_model(
        self,
        *,
        team_id: uuid.UUID,
        name: str,
        capability: str,
        real_model: str,
        credential_id: uuid.UUID,
        provider: str,
        weight: int,
        rpm_limit: int | None,
        tpm_limit: int | None,
        tags: dict[str, Any] | None,
        is_platform_admin: bool,
        enabled: bool = True,
        reload_router: bool = True,
    ) -> Any:
        raw_rm = str(real_model).strip()
        if not raw_rm:
            raise ValidationError("上游模型 ID 不能为空")
        cred = await self._creds.get_bindable_for_team_gateway_model(
            credential_id,
            team_id=team_id,
            is_platform_admin=is_platform_admin,
        )
        if cred is None:
            raise CredentialNotFoundError(str(credential_id))
        prov_norm = provider.strip().lower()
        if cred.provider.strip().lower() != prov_norm:
            raise ValidationError(
                f"凭据提供商为 {cred.provider}，与请求的 provider {provider} 不一致"
            )
        prefix_msg = litellm_prefix_violation_message(provider, raw_rm)
        if prefix_msg:
            raise ValidationError(prefix_msg)
        normalized_rm = build_litellm_model_id(provider, raw_rm)
        row = await self._models.create(
            team_id=team_id,
            name=name,
            capability=capability,
            real_model=normalized_rm,
            credential_id=credential_id,
            provider=provider,
            weight=weight,
            rpm_limit=rpm_limit,
            tpm_limit=tpm_limit,
            tags=tags,
            enabled=enabled,
        )
        if reload_router:
            await self.reload_litellm_router()
        return row

    async def create_multi_credential_gateway_model(
        self,
        *,
        team_id: uuid.UUID,
        name: str,
        capability: str,
        real_model: str,
        provider: str,
        credential_ids: list[uuid.UUID],
        is_platform_admin: bool,
        strategy: str = "simple-shuffle",
        weight: int = 1,
        rpm_limit: int | None = None,
        tpm_limit: int | None = None,
        tags: dict[str, Any] | None = None,
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
        if await repo.name_exists_on_team(team_id, cleaned_name):
            raise ValidationError(f"虚拟模型名 {cleaned_name} 与现有 GatewayModel 别名冲突")
        existing_route = await self._routes.get_by_virtual_model(team_id, cleaned_name)
        if existing_route is not None:
            raise ValidationError(f"虚拟模型名 {cleaned_name} 已存在 GatewayRoute")

        from domains.gateway.infrastructure.models.gateway_model import GatewayModel

        created_models: list[GatewayModel] = []
        route = None
        try:
            for cid in credential_ids:
                short = uuid.UUID(str(cid)).hex[:8]
                alias = f"{cleaned_name}--{short}"
                suffix = 0
                base_alias = alias
                while await repo.name_exists_on_team(team_id, alias):
                    suffix += 1
                    alias = f"{base_alias}-{suffix}"
                row = await self.create_gateway_model(
                    team_id=team_id,
                    name=alias,
                    capability=capability,
                    real_model=real_model,
                    credential_id=cid,
                    provider=provider,
                    weight=weight,
                    rpm_limit=rpm_limit,
                    tpm_limit=tpm_limit,
                    tags=tags,
                    is_platform_admin=is_platform_admin,
                    enabled=enabled,
                    reload_router=False,
                )
                created_models.append(row)
            route = await self._routes.create(
                team_id=team_id,
                virtual_model=cleaned_name,
                primary_models=[m.name for m in created_models],
                strategy=strategy_norm,
            )
        except Exception:
            for r in created_models:
                with suppress(Exception):
                    await repo.delete(r.id)
            raise
        await self.reload_litellm_router()
        assert route is not None
        return MultiCredentialGatewayModelResult(route=route, models=created_models)

    async def update_gateway_model(
        self,
        model_id: uuid.UUID,
        *,
        team_id: uuid.UUID,
        is_platform_admin: bool,
        fields: dict[str, Any],
    ) -> Any:
        repo = self._models
        existing = await repo.get(model_id)
        if existing is None or (existing.team_id is not None and existing.team_id != team_id):
            raise ManagementEntityNotFoundError("model", str(model_id))

        update_fields = dict(fields)
        if "credential_id" in update_fields and update_fields["credential_id"] is not None:
            new_cid_raw = update_fields["credential_id"]
            new_cid = (
                new_cid_raw if isinstance(new_cid_raw, uuid.UUID) else uuid.UUID(str(new_cid_raw))
            )
            cred = await self._creds.get_bindable_for_team_gateway_model(
                new_cid,
                team_id=team_id,
                is_platform_admin=is_platform_admin,
            )
            if cred is None:
                raise CredentialNotFoundError(str(new_cid))
            if cred.provider.strip().lower() != existing.provider.strip().lower():
                raise ValidationError(
                    f"凭据提供商为 {cred.provider}，与当前模型的 provider（{existing.provider}）不一致"
                )
        if "real_model" in update_fields and update_fields["real_model"] is not None:
            raw_rm = str(update_fields["real_model"]).strip()
            if not raw_rm:
                raise ValidationError("上游模型 ID 不能为空")
            prefix_msg = litellm_prefix_violation_message(existing.provider, raw_rm)
            if prefix_msg:
                raise ValidationError(prefix_msg)
            update_fields["real_model"] = build_litellm_model_id(existing.provider, raw_rm)

        new_name_raw = update_fields.get("name")
        if new_name_raw is not None:
            new_name = str(new_name_raw).strip()
            if not new_name:
                raise ValidationError("注册别名不能为空")
            update_fields["name"] = new_name
            if new_name != existing.name:
                tags = existing.tags or {}
                if (
                    existing.team_id is None
                    and tags.get(GATEWAY_MODEL_MANAGED_BY_TAG) == CONFIG_MANAGED_BY
                ):
                    raise ValidationError("配置托管的系统模型不可修改注册别名")
                owner_team_id = existing.team_id
                if await repo.name_exists_in_scope(owner_team_id, new_name, exclude_id=model_id):
                    raise ValidationError(f"注册别名已存在: {new_name}")
                await rename_gateway_model_name_references(
                    self._session,
                    team_id=owner_team_id,
                    old_name=existing.name,
                    new_name=new_name,
                )

        updated = await repo.update(model_id, **update_fields)
        if updated is None:
            raise ManagementEntityNotFoundError("model", str(model_id))
        await self.reload_litellm_router()
        return updated

    async def delete_gateway_model(self, model_id: uuid.UUID, *, team_id: uuid.UUID) -> None:
        repo = self._models
        existing = await repo.get(model_id)
        if existing is None or (existing.team_id is not None and existing.team_id != team_id):
            raise CredentialNotFoundError(str(model_id))
        model_name = existing.name
        await repo.delete(model_id)
        await prune_gateway_model_name_references(self._session, frozenset({model_name}))
        await self.reload_litellm_router()

    async def test_gateway_model(
        self,
        model_id: uuid.UUID,
        *,
        team_id: uuid.UUID,
    ) -> dict[str, Any]:
        """对 Gateway 团队模型发起一次最小调用做连通性测试（chat / embedding / 生图）。

        - 仅支持 ``GATEWAY_MODEL_TEST_SUPPORTED_CAPABILITIES`` 中的 capability；
          其它返回 ``success=false`` + ``status=failed`` 并写回字段，避免前端误以为"未测过"。
        - 直连 ``litellm.acompletion`` / ``litellm.aimage_generation`` /
          ``litellm.aembedding`` 并显式传入解密后的 ``api_key`` 与 ``api_base``，
          绕过 Gateway 内部桥接，确保探测的就是这条记录本身的凭据。
        无论成功/失败，均把 ``last_test_status`` + ``last_tested_at`` +
        ``last_test_reason`` 写回 ``gateway_models``，列表页可直接展示连通状态。
        """
        existing = await self._models.get(model_id)
        if existing is None or (existing.team_id is not None and existing.team_id != team_id):
            raise ManagementEntityNotFoundError("model", str(model_id))

        capability = existing.capability
        litellm_model = build_litellm_model_id(existing.provider, existing.real_model)
        tested_at = datetime.now(UTC)

        if capability not in GATEWAY_MODEL_TEST_SUPPORTED_CAPABILITIES:
            msg = f"capability={capability} 暂不支持连通性测试"
            return await _record_gateway_model_test_failure(
                self._models, model_id, tested_at, msg, litellm_model
            )

        credential = await self._creds.get(existing.credential_id)
        if credential is None:
            msg = "关联凭据已不存在"
            return await _record_gateway_model_test_failure(
                self._models, model_id, tested_at, msg, litellm_model
            )

        encryption_key = derive_encryption_key(_settings.secret_key.get_secret_value())
        try:
            api_key = decrypt_value(credential.api_key_encrypted, encryption_key)
        except Exception as exc:  # pragma: no cover - 极端配置异常
            logger.warning("Failed to decrypt credential %s: %s", credential.id, exc)
            msg = f"凭据解密失败: {exc}"
            return await _record_gateway_model_test_failure(
                self._models, model_id, tested_at, msg, litellm_model
            )

        api_base = credential.api_base
        # 延迟导入 litellm，避免在模块加载阶段拉起重型依赖。
        from litellm import (  # pylint: disable=import-error,import-outside-toplevel
            acompletion,
            aembedding,
            aimage_generation,
        )

        try:
            if capability == "chat":
                response = await acompletion(
                    model=litellm_model,
                    messages=[{"role": "user", "content": "Hi"}],
                    max_tokens=10,
                    temperature=0,
                    api_key=api_key,
                    api_base=api_base,
                )
                preview = ""
                with suppress(Exception):
                    preview = (response.choices[0].message.content or "")[:100]
                return await _record_gateway_model_test_success(
                    self._models,
                    model_id,
                    tested_at,
                    litellm_model,
                    response_preview=preview,
                )

            if capability == "image":
                img_size = _gateway_image_probe_size(existing.provider)
                img_response = await aimage_generation(
                    model=litellm_model,
                    prompt="ping",
                    n=1,
                    size=img_size,
                    api_key=api_key,
                    api_base=api_base,
                    timeout=60,
                )
                preview = _image_generation_probe_preview(img_response)
                return await _record_gateway_model_test_success(
                    self._models,
                    model_id,
                    tested_at,
                    litellm_model,
                    response_preview=preview,
                )

            if capability == "embedding":
                await aembedding(
                    model=litellm_model,
                    input=["ping"],
                    api_key=api_key,
                    api_base=api_base,
                )
                return await _record_gateway_model_test_success(
                    self._models, model_id, tested_at, litellm_model
                )

            raise AssertionError(
                f"test_gateway_model: capability {capability!r} missing probe branch "
                f"(out of sync with GATEWAY_MODEL_TEST_SUPPORTED_CAPABILITIES)"
            )
        except Exception as exc:
            logger.warning("Gateway model %s connection test failed: %s", model_id, exc)
            msg = f"连接失败: {exc}"
            return await _record_gateway_model_test_failure(
                self._models, model_id, tested_at, msg, litellm_model
            )

    async def create_gateway_route(
        self,
        *,
        team_id: uuid.UUID,
        virtual_model: str,
        primary_models: list[str],
        fallbacks_general: list[str],
        fallbacks_content_policy: list[str],
        fallbacks_context_window: list[str],
        strategy: str,
        retry_policy: dict[str, Any],
    ) -> Any:
        row = await self._routes.create(
            team_id=team_id,
            virtual_model=virtual_model,
            primary_models=primary_models,
            fallbacks_general=fallbacks_general,
            fallbacks_content_policy=fallbacks_content_policy,
            fallbacks_context_window=fallbacks_context_window,
            strategy=validate_routing_strategy(strategy),
            retry_policy=retry_policy,
        )
        await self.reload_litellm_router()
        return row

    async def update_gateway_route(
        self,
        route_id: uuid.UUID,
        *,
        team_id: uuid.UUID,
        fields: dict[str, Any],
    ) -> Any:
        repo = self._routes
        existing = await repo.get(route_id)
        if existing is None or (existing.team_id is not None and existing.team_id != team_id):
            raise ManagementEntityNotFoundError("route", str(route_id))
        patch = dict(fields)
        if patch.get("strategy") is not None:
            patch["strategy"] = validate_routing_strategy(str(patch["strategy"]))
        updated = await repo.update(route_id, **patch)
        if updated is None:
            raise ManagementEntityNotFoundError("route", str(route_id))
        await self.reload_litellm_router()
        return updated

    async def delete_gateway_route(self, route_id: uuid.UUID, *, team_id: uuid.UUID) -> None:
        repo = self._routes
        existing = await repo.get(route_id)
        if existing is None or (existing.team_id is not None and existing.team_id != team_id):
            raise ManagementEntityNotFoundError("route", str(route_id))
        await repo.delete(route_id)
        await self.reload_litellm_router()

    async def reload_litellm_router(self) -> None:
        from domains.gateway.infrastructure.router_singleton import reload_router

        with suppress(Exception):  # pragma: no cover
            await reload_router(self._session)

    async def upsert_budget(
        self,
        *,
        scope: str,
        scope_id: uuid.UUID | None,
        period: str,
        model_name: str | None = None,
        limit_usd: Decimal | None,
        soft_limit_usd: Decimal | None = None,
        limit_tokens: int | None,
        limit_requests: int | None,
    ) -> Any:
        return await self._budgets.upsert(
            scope=scope,
            scope_id=scope_id,
            period=period,
            model_name=model_name,
            limit_usd=limit_usd,
            soft_limit_usd=soft_limit_usd,
            limit_tokens=limit_tokens,
            limit_requests=limit_requests,
        )

    async def delete_budget(self, budget_id: uuid.UUID) -> None:
        await self._budgets.delete(budget_id)

    async def create_alert_rule(
        self,
        *,
        team_id: uuid.UUID,
        name: str,
        description: str | None,
        metric: str,
        threshold: Decimal,
        window_minutes: int,
        channels: dict[str, Any],
        enabled: bool,
    ) -> GatewayAlertRule:
        return await self._alerts.create_rule(
            team_id=team_id,
            name=name,
            description=description,
            metric=metric,
            threshold=threshold,
            window_minutes=window_minutes,
            channels=channels,
            enabled=enabled,
        )

    async def update_alert_rule(
        self,
        rule_id: uuid.UUID,
        *,
        team_id: uuid.UUID,
        fields: dict[str, Any],
    ) -> GatewayAlertRule:
        rule = await self._alerts.get_rule(rule_id)
        if rule is None or rule.team_id != team_id:
            raise ManagementEntityNotFoundError("alert_rule", str(rule_id))
        return await self._alerts.update_rule_fields(rule, fields)

    async def delete_alert_rule(self, rule_id: uuid.UUID, *, team_id: uuid.UUID) -> None:
        rule = await self._alerts.get_rule(rule_id)
        if rule is None or rule.team_id != team_id:
            raise ManagementEntityNotFoundError("alert_rule", str(rule_id))
        await self._alerts.delete_rule(rule)

    # ------------------------------------------------------------------
    # ProviderPlan / EntitlementPlan CRUD
    #
    # 路由层只做编排，归属/团队校验集中在此（与凭据/告警写侧一致），避免
    # 跨团队 IDOR；scope=vkey 校验 vkey.team_id；scope=apikey_grant 校验 grant.team_id。
    # ------------------------------------------------------------------
    async def _assert_credential_in_team(
        self,
        credential_id: uuid.UUID,
        *,
        team_id: uuid.UUID,
        is_platform_admin: bool,
    ) -> None:
        """与 ``list_credentials_for_team`` 可见集合一致：team-scope 凭据 + 平台管理员可见 system。"""
        row = await self._creds.get_bindable_for_team_gateway_model(
            credential_id,
            team_id=team_id,
            is_platform_admin=is_platform_admin,
        )
        if row is None:
            raise CredentialNotFoundError(str(credential_id))

    async def _assert_provider_plan_in_credential(
        self,
        plan_id: uuid.UUID,
        *,
        credential_id: uuid.UUID,
    ) -> ProviderPlan:
        plan = await self._provider_plans.get(plan_id)
        if plan is None or plan.credential_id != credential_id:
            raise ManagementEntityNotFoundError("provider_plan", str(plan_id))
        return plan

    async def _assert_vkey_in_team(
        self,
        vkey_id: uuid.UUID,
        *,
        team_id: uuid.UUID,
        is_platform_admin: bool,
    ) -> None:
        record = await self._vkeys.get(vkey_id)
        if record is None:
            raise VirtualKeyNotFoundError(str(vkey_id))
        if not is_platform_admin and record.team_id != team_id:
            # 与 vkey 列表一致：未授权直接返回 404，避免泄露存在性。
            raise VirtualKeyNotFoundError(str(vkey_id))

    async def _assert_apikey_grant_in_team(
        self,
        grant_id: uuid.UUID,
        *,
        team_id: uuid.UUID,
        is_platform_admin: bool,
    ) -> None:
        from sqlalchemy import select

        from domains.identity.infrastructure.models.api_key import ApiKeyGatewayGrant

        stmt = select(ApiKeyGatewayGrant).where(ApiKeyGatewayGrant.id == grant_id)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            raise ManagementEntityNotFoundError("apikey_grant", str(grant_id))
        if not is_platform_admin and row.team_id != team_id:
            raise ManagementEntityNotFoundError("apikey_grant", str(grant_id))

    async def _assert_entitlement_plan_in_team(
        self,
        plan_id: uuid.UUID,
        *,
        team_id: uuid.UUID,
        is_platform_admin: bool,
    ) -> EntitlementPlan:
        plan = await self._entitlement_plans.get(plan_id)
        if plan is None:
            raise ManagementEntityNotFoundError("entitlement_plan", str(plan_id))
        if plan.scope == "vkey":
            await self._assert_vkey_in_team(
                plan.scope_id, team_id=team_id, is_platform_admin=is_platform_admin
            )
        elif plan.scope == "apikey_grant":
            await self._assert_apikey_grant_in_team(
                plan.scope_id, team_id=team_id, is_platform_admin=is_platform_admin
            )
        else:
            raise ManagementEntityNotFoundError("entitlement_plan", str(plan_id))
        return plan

    async def create_provider_plan(
        self,
        *,
        credential_id: uuid.UUID,
        team_id: uuid.UUID,
        is_platform_admin: bool,
        real_model: str | None,
        label: str,
        valid_from: datetime,
        valid_until: datetime,
        is_active: bool = True,
        auto_renew: bool = False,
        notes: str | None = None,
        extra: dict[str, Any] | None = None,
        quotas: list[dict[str, Any]] | None = None,
    ) -> ProviderPlan:
        await self._assert_credential_in_team(
            credential_id, team_id=team_id, is_platform_admin=is_platform_admin
        )
        plan = await self._provider_plans.create(
            credential_id=credential_id,
            real_model=real_model,
            label=label,
            valid_from=valid_from,
            valid_until=valid_until,
            is_active=is_active,
            auto_renew=auto_renew,
            notes=notes,
            extra=extra,
        )
        for q in quotas or []:
            await self._provider_plans.add_quota(plan_id=plan.id, **q)
        return plan

    async def update_provider_plan(
        self,
        plan_id: uuid.UUID,
        *,
        credential_id: uuid.UUID,
        team_id: uuid.UUID,
        is_platform_admin: bool,
        fields: dict[str, Any],
        quotas: list[dict[str, Any]] | None = None,
    ) -> ProviderPlan:
        await self._assert_credential_in_team(
            credential_id, team_id=team_id, is_platform_admin=is_platform_admin
        )
        await self._assert_provider_plan_in_credential(plan_id, credential_id=credential_id)
        await self._provider_plans.update(plan_id, **fields)
        if quotas is not None:
            await self._provider_plans.replace_quotas(plan_id, quotas)
        result = await self._provider_plans.get(plan_id)
        if result is None:
            raise ManagementEntityNotFoundError("provider_plan", str(plan_id))
        return result

    async def delete_provider_plan(
        self,
        plan_id: uuid.UUID,
        *,
        credential_id: uuid.UUID,
        team_id: uuid.UUID,
        is_platform_admin: bool,
    ) -> None:
        await self._assert_credential_in_team(
            credential_id, team_id=team_id, is_platform_admin=is_platform_admin
        )
        await self._assert_provider_plan_in_credential(plan_id, credential_id=credential_id)
        ok = await self._provider_plans.delete(plan_id)
        if not ok:
            raise ManagementEntityNotFoundError("provider_plan", str(plan_id))

    async def create_entitlement_plan(
        self,
        *,
        scope: str,
        scope_id: uuid.UUID,
        team_id: uuid.UUID,
        is_platform_admin: bool,
        label: str,
        valid_from: datetime,
        valid_until: datetime,
        included_models: list[str] | None = None,
        included_capabilities: list[str] | None = None,
        is_active: bool = True,
        auto_renew: bool = False,
        notes: str | None = None,
        extra: dict[str, Any] | None = None,
        quotas: list[dict[str, Any]] | None = None,
    ) -> EntitlementPlan:
        if scope == "vkey":
            await self._assert_vkey_in_team(
                scope_id, team_id=team_id, is_platform_admin=is_platform_admin
            )
        elif scope == "apikey_grant":
            await self._assert_apikey_grant_in_team(
                scope_id, team_id=team_id, is_platform_admin=is_platform_admin
            )
        else:
            raise ValidationError(f"不支持的 entitlement scope: {scope}")
        plan = await self._entitlement_plans.create(
            scope=scope,
            scope_id=scope_id,
            label=label,
            valid_from=valid_from,
            valid_until=valid_until,
            included_models=included_models,
            included_capabilities=included_capabilities,
            is_active=is_active,
            auto_renew=auto_renew,
            notes=notes,
            extra=extra,
        )
        for q in quotas or []:
            await self._entitlement_plans.add_quota(plan_id=plan.id, **q)
        return plan

    async def update_entitlement_plan(
        self,
        plan_id: uuid.UUID,
        *,
        team_id: uuid.UUID,
        is_platform_admin: bool,
        fields: dict[str, Any],
        quotas: list[dict[str, Any]] | None = None,
    ) -> EntitlementPlan:
        await self._assert_entitlement_plan_in_team(
            plan_id, team_id=team_id, is_platform_admin=is_platform_admin
        )
        await self._entitlement_plans.update(plan_id, **fields)
        if quotas is not None:
            await self._entitlement_plans.replace_quotas(plan_id, quotas)
        result = await self._entitlement_plans.get(plan_id)
        if result is None:
            raise ManagementEntityNotFoundError("entitlement_plan", str(plan_id))
        return result

    async def delete_entitlement_plan(
        self,
        plan_id: uuid.UUID,
        *,
        team_id: uuid.UUID,
        is_platform_admin: bool,
    ) -> None:
        await self._assert_entitlement_plan_in_team(
            plan_id, team_id=team_id, is_platform_admin=is_platform_admin
        )
        ok = await self._entitlement_plans.delete(plan_id)
        if not ok:
            raise ManagementEntityNotFoundError("entitlement_plan", str(plan_id))

    async def upsert_upstream_pricing(
        self,
        *,
        provider: str,
        upstream_model: str,
        capability: str,
        currency: str,
        amount_per_million: dict[str, Any],
    ):
        from domains.gateway.application.pricing.pricing_management import parse_amount_per_million
        from domains.gateway.application.pricing.pricing_service import PricingService
        from domains.gateway.infrastructure.fx.fx_static import build_static_fx_adapter
        from domains.gateway.infrastructure.repositories.pricing_repository import (
            DownstreamPricingRepository,
            UpstreamPricingRepository,
        )

        fx = build_static_fx_adapter()
        inp, out, cc, cr, extra = parse_amount_per_million(amount_per_million, currency, fx)
        repo = UpstreamPricingRepository(self._session)
        now = datetime.now(UTC)
        existing = await repo.get_active(
            provider=provider,
            upstream_model=upstream_model,
            capability=capability,
            at=now,
        )
        version = 1
        if existing is not None:
            await repo.close_effective(existing, at=now)
            version = existing.version + 1
        row = await repo.create(
            provider=provider,
            upstream_model=upstream_model,
            capability=capability,
            input_cost_per_token=inp,
            output_cost_per_token=out,
            cache_creation_input_token_cost=cc,
            cache_read_input_token_cost=cr,
            extra=extra,
            source="manual",
            effective_from=now,
            version=version,
        )
        svc = PricingService(repo, DownstreamPricingRepository(self._session))
        await svc.sync_to_litellm_registry()
        from domains.gateway.application.pricing.pricing_resolution_cache import (
            invalidate_pricing_resolution_cache,
        )

        await invalidate_pricing_resolution_cache()
        return row

    async def sync_upstream_from_litellm(self, providers: Iterable[str] | None = None):
        from domains.gateway.application.pricing.litellm_upstream_price_sync import (
            LitellmUpstreamPriceSyncService,
        )
        from domains.gateway.application.pricing.pricing_resolution_cache import (
            invalidate_pricing_resolution_cache,
        )
        from domains.gateway.application.pricing.pricing_service import PricingService
        from domains.gateway.infrastructure.repositories.model_repository import (
            GatewayModelRepository,
        )
        from domains.gateway.infrastructure.repositories.pricing_repository import (
            DownstreamPricingRepository,
            UpstreamPricingRepository,
        )

        upstream_repo = UpstreamPricingRepository(self._session)
        if providers is None:
            summaries = await self._creds.list_effective_provider_summaries()
            allowed_providers = {s.provider for s in summaries}
        else:
            allowed_providers = {p for p in providers if p}
        models = await GatewayModelRepository(self._session).list_for_team(None, only_enabled=False)
        gateway_models = [
            (m.provider, m.real_model, str(m.capability or "chat")) for m in models if m.real_model
        ]
        report = await LitellmUpstreamPriceSyncService(upstream_repo).sync_from_litellm_model_cost(
            gateway_models=gateway_models,
            allowed_providers=allowed_providers,
        )
        pricing_svc = PricingService(upstream_repo, DownstreamPricingRepository(self._session))
        await pricing_svc.sync_to_litellm_registry()
        await invalidate_pricing_resolution_cache()
        return report

    async def upsert_downstream_pricing(
        self,
        *,
        scope: str,
        scope_id: uuid.UUID | None,
        gateway_model_id: uuid.UUID | None,
        inheritance_strategy: str,
        currency: str = "CNY",
        amount_per_million: dict[str, Any] | None = None,
    ):
        from domains.gateway.infrastructure.repositories.pricing_repository import (
            DownstreamPricingRepository,
        )

        repo = DownstreamPricingRepository(self._session)
        now = datetime.now(UTC)
        existing = await repo.get_active_for_scope(
            scope=scope,
            scope_id=scope_id,
            gateway_model_id=gateway_model_id,
            at=now,
        )
        version = 1
        if existing is not None:
            await repo.close_effective(existing, at=now)
            version = existing.version + 1
        if inheritance_strategy == "mirror":
            row = await repo.create(
                scope=scope,
                scope_id=scope_id,
                gateway_model_id=gateway_model_id,
                inheritance_strategy="mirror",
                effective_from=now,
                version=version,
            )
            from domains.gateway.application.pricing.pricing_resolution_cache import (
                invalidate_pricing_resolution_cache,
            )

            await invalidate_pricing_resolution_cache(
                team_id=scope_id if scope == "team" else None,
                gateway_model_id=gateway_model_id,
            )
            return row
        if amount_per_million is None:
            raise ValidationError("manual downstream pricing requires amount_per_million")
        from domains.gateway.application.pricing.pricing_management import parse_amount_per_million
        from domains.gateway.infrastructure.fx.fx_static import build_static_fx_adapter

        fx = build_static_fx_adapter()
        inp, out, cc, cr, extra = parse_amount_per_million(amount_per_million, currency, fx)
        per_request_raw = amount_per_million.get("per_request")
        per_request_usd: Decimal | None = None
        if per_request_raw is not None:
            from decimal import Decimal

            per_request_usd = Decimal(str(per_request_raw))
            if currency.upper() == "CNY":
                per_request_usd = per_request_usd * fx.get_rate("CNY", "USD")
        row = await repo.create(
            scope=scope,
            scope_id=scope_id,
            gateway_model_id=gateway_model_id,
            inheritance_strategy="manual",
            input_cost_per_token=inp,
            output_cost_per_token=out,
            cache_creation_input_token_cost=cc,
            cache_read_input_token_cost=cr,
            per_request_usd=per_request_usd,
            extra=extra,
            effective_from=now,
            version=version,
        )
        from domains.gateway.application.pricing.pricing_resolution_cache import (
            invalidate_pricing_resolution_cache,
        )

        await invalidate_pricing_resolution_cache(
            team_id=scope_id if scope == "team" else None,
            gateway_model_id=gateway_model_id,
        )
        return row


__all__ = ["GatewayManagementWriteService"]
