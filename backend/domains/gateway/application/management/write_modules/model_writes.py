"""Gateway 管理面变更应用服务（写侧分包；对外 API 不变）。"""

from __future__ import annotations

from contextlib import suppress
from typing import Any
import uuid

from domains.gateway.application.litellm_real_model_prefix import litellm_prefix_violation_message
from domains.gateway.application.management.multi_credential_types import (
    MultiCredentialGatewayModelResult,
)
from domains.gateway.application.model_reference_prune import (
    prune_gateway_model_name_references,
    rename_gateway_model_name_references,
)
from domains.gateway.application.routing_strategy_validation import validate_routing_strategy
from domains.gateway.domain.errors import (
    CredentialNotFoundError,
    ManagementEntityNotFoundError,
)
from domains.gateway.domain.types import (
    CONFIG_MANAGED_BY,
    GATEWAY_MODEL_MANAGED_BY_TAG,
    PERSONAL_MODEL_PROVIDERS,
    PERSONAL_MODEL_TYPES,
)
from libs.exceptions import ValidationError
from libs.llm.litellm_model_id import build_litellm_model_id
from utils.logging import get_logger

logger = get_logger(__name__)



class ModelWritesMixin:
    """写侧 mixin — 由 GatewayManagementWriteService 组合。"""

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
            mtags['display_name'] = display_name
            if tags:
                mtags.update({k: v for k, v in tags.items() if v is not None})
            row = await self._models.create(team_id=team_id, name=alias, capability=cap, real_model=real_model, credential_id=credential_id, provider=provider, weight=1, rpm_limit=None, tpm_limit=None, tags=mtags, enabled=enabled)
            created.append(row)
        if reload_router:
            await self.reload_litellm_router()
        return created

    async def update_personal_model(self, user_id: uuid.UUID, model_id: uuid.UUID, fields: dict[str, Any]) -> Any:
        team_id = await self._ensure_personal_team_id(user_id)
        existing = await self._models.get_on_team(model_id, team_id)
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
        await self.reload_litellm_router()
        return updated

    async def delete_personal_model(self, user_id: uuid.UUID, model_id: uuid.UUID) -> None:
        team_id = await self._ensure_personal_team_id(user_id)
        existing = await self._models.get_on_team(model_id, team_id)
        if existing is None:
            raise ManagementEntityNotFoundError('model', str(model_id))
        model_name = existing.name
        await self._models.delete(model_id)
        await prune_gateway_model_name_references(self._session, frozenset({model_name}))
        await self.reload_litellm_router()

    async def create_gateway_model(self, *, team_id: uuid.UUID, name: str, capability: str, real_model: str, credential_id: uuid.UUID, provider: str, weight: int, rpm_limit: int | None, tpm_limit: int | None, tags: dict[str, Any] | None, is_platform_admin: bool, enabled: bool=True, reload_router: bool=True) -> Any:
        raw_rm = str(real_model).strip()
        if not raw_rm:
            raise ValidationError('上游模型 ID 不能为空')
        cred = await self._creds.get_bindable_for_team_gateway_model(credential_id, team_id=team_id, is_platform_admin=is_platform_admin)
        if cred is None:
            raise CredentialNotFoundError(str(credential_id))
        prov_norm = provider.strip().lower()
        if cred.provider.strip().lower() != prov_norm:
            raise ValidationError(f'凭据提供商为 {cred.provider}，与请求的 provider {provider} 不一致')
        prefix_msg = litellm_prefix_violation_message(provider, raw_rm)
        if prefix_msg:
            raise ValidationError(prefix_msg)
        normalized_rm = build_litellm_model_id(provider, raw_rm)
        row = await self._models.create(team_id=team_id, name=name, capability=capability, real_model=normalized_rm, credential_id=credential_id, provider=provider, weight=weight, rpm_limit=rpm_limit, tpm_limit=tpm_limit, tags=tags, enabled=enabled)
        if reload_router:
            await self.reload_litellm_router()
        return row

    async def create_multi_credential_gateway_model(self, *, team_id: uuid.UUID, name: str, capability: str, real_model: str, provider: str, credential_ids: list[uuid.UUID], is_platform_admin: bool, strategy: str='simple-shuffle', weight: int=1, rpm_limit: int | None=None, tpm_limit: int | None=None, tags: dict[str, Any] | None=None, enabled: bool=True) -> MultiCredentialGatewayModelResult:
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
        if await repo.name_exists_on_team(team_id, cleaned_name):
            raise ValidationError(f'虚拟模型名 {cleaned_name} 与现有 GatewayModel 别名冲突')
        existing_route = await self._routes.get_by_virtual_model(team_id, cleaned_name)
        if existing_route is not None:
            raise ValidationError(f'虚拟模型名 {cleaned_name} 已存在 GatewayRoute')
        from domains.gateway.infrastructure.models.gateway_model import GatewayModel
        created_models: list[GatewayModel] = []
        route = None
        try:
            for cid in credential_ids:
                short = uuid.UUID(str(cid)).hex[:8]
                alias = f'{cleaned_name}--{short}'
                suffix = 0
                base_alias = alias
                while await repo.name_exists_on_team(team_id, alias):
                    suffix += 1
                    alias = f'{base_alias}-{suffix}'
                row = await self.create_gateway_model(team_id=team_id, name=alias, capability=capability, real_model=real_model, credential_id=cid, provider=provider, weight=weight, rpm_limit=rpm_limit, tpm_limit=tpm_limit, tags=tags, is_platform_admin=is_platform_admin, enabled=enabled, reload_router=False)
                created_models.append(row)
            route = await self._routes.create(team_id=team_id, virtual_model=cleaned_name, primary_models=[m.name for m in created_models], strategy=strategy_norm)
        except Exception:
            for r in created_models:
                with suppress(Exception):
                    await repo.delete(r.id)
            raise
        await self.reload_litellm_router()
        assert route is not None
        return MultiCredentialGatewayModelResult(route=route, models=created_models)

    async def update_gateway_model(self, model_id: uuid.UUID, *, team_id: uuid.UUID, is_platform_admin: bool, fields: dict[str, Any]) -> Any:
        repo = self._models
        existing = await repo.get(model_id)
        if existing is None or (existing.team_id is not None and existing.team_id != team_id):
            raise ManagementEntityNotFoundError('model', str(model_id))
        update_fields = dict(fields)
        if 'credential_id' in update_fields and update_fields['credential_id'] is not None:
            new_cid_raw = update_fields['credential_id']
            new_cid = new_cid_raw if isinstance(new_cid_raw, uuid.UUID) else uuid.UUID(str(new_cid_raw))
            cred = await self._creds.get_bindable_for_team_gateway_model(new_cid, team_id=team_id, is_platform_admin=is_platform_admin)
            if cred is None:
                raise CredentialNotFoundError(str(new_cid))
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
        new_name_raw = update_fields.get('name')
        if new_name_raw is not None:
            new_name = str(new_name_raw).strip()
            if not new_name:
                raise ValidationError('注册别名不能为空')
            update_fields['name'] = new_name
            if new_name != existing.name:
                tags = existing.tags or {}
                if existing.team_id is None and tags.get(GATEWAY_MODEL_MANAGED_BY_TAG) == CONFIG_MANAGED_BY:
                    raise ValidationError('配置托管的系统模型不可修改注册别名')
                owner_team_id = existing.team_id
                if await repo.name_exists_in_scope(owner_team_id, new_name, exclude_id=model_id):
                    raise ValidationError(f'注册别名已存在: {new_name}')
                await rename_gateway_model_name_references(self._session, team_id=owner_team_id, old_name=existing.name, new_name=new_name)
        updated = await repo.update(model_id, **update_fields)
        if updated is None:
            raise ManagementEntityNotFoundError('model', str(model_id))
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
