"""ModelCatalogPort 的 Gateway DB 实现。"""

from __future__ import annotations

from typing import Any
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from bootstrap.config import settings
from domains.gateway.application.config_catalog_sync import (
    gateway_model_to_selector_item,
    model_types_for_gateway_registration,
)
from domains.gateway.application.entitlement_model_status import is_connectivity_requestable
from domains.gateway.application.gateway_model_listing import (
    _registry_row_deployable,
    list_merged_models_for_tenant,
)
from domains.gateway.application.internal_bridge_actor import resolve_internal_gateway_team_id
from domains.gateway.application.model_catalog_port import (
    ModelCapabilitySnapshot,
    ModelCatalogPort,
    RegisteredModelResolution,
)
from domains.gateway.application.personal_models import gateway_model_to_selector_user_item
from domains.gateway.domain.litellm_model_id import build_litellm_model_id
from domains.gateway.domain.model_capability import tags_to_capability_snapshot
from domains.gateway.infrastructure.models.gateway_model import GatewayModel
from domains.gateway.infrastructure.repositories.credential_repository import (
    ProviderCredentialRepository,
)
from domains.gateway.infrastructure.repositories.model_repository import GatewayModelRepository
from domains.tenancy.application.team_service import TeamService
from libs.crypto import decrypt_value, derive_encryption_key


class SqlModelCatalogAdapter:
    """以 ``GatewayModel`` 为运行时目录唯一真源；列表不回退 app.toml。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._models = GatewayModelRepository(session)
        self._creds = ProviderCredentialRepository(session)
        self._teams = TeamService(session)
        self._encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())

    async def list_visible_models(
        self,
        *,
        billing_team_id: uuid.UUID | None,
        model_type: str | None,
        user_id: uuid.UUID | None = None,
    ) -> list[dict[str, Any]]:
        rows = await list_merged_models_for_tenant(
            self._session,
            billing_team_id,
            only_enabled=True,
            user_id=user_id,
        )
        # 仓储已按「团队行先于全局行」排序；同名只保留第一条（团队覆盖全局）
        by_name: dict[str, GatewayModel] = {}
        for row in rows:
            if row.name not in by_name:
                by_name[row.name] = row
        items: list[dict[str, Any]] = []
        for row in sorted(by_name.values(), key=lambda r: r.name):
            # 与 resolve_by_name_visible / Router 注册一致：凭据须可部署
            if not await _registry_row_deployable(self._session, row):
                continue
            # 与模型选择器一致：已知连通性测试失败的模型不进入「可用」目录，
            # 避免管理页标「不可用」但对话/产品信息仍可点选。
            if not is_connectivity_requestable(row.last_test_status):
                continue
            item = gateway_model_to_selector_item(row)
            if model_type and model_type not in item["model_types"]:
                continue
            items.append(item)
        return items

    async def list_personal_models_for_selector(
        self,
        user_id: uuid.UUID,
        model_type: str | None,
        provider: str | None,
    ) -> list[dict[str, Any]]:
        personal_team = await self._teams.ensure_personal_team(user_id)
        rows = await self._models.list_tenant_owned(
            personal_team.id,
            only_enabled=True,
            provider=provider,
        )
        items: list[dict[str, Any]] = []
        for row in rows:
            if not is_connectivity_requestable(row.last_test_status):
                continue
            item = gateway_model_to_selector_user_item(row)
            if model_type and model_type not in item["model_types"]:
                continue
            items.append(item)
        return items

    async def resolve_registered_model(
        self,
        user_id: uuid.UUID,
        model_ref: uuid.UUID,
        required_model_type: str | None,
    ) -> RegisteredModelResolution | None:
        personal_team = await self._teams.ensure_personal_team(user_id)
        tenant_id = personal_team.id

        direct = await self._models.get_for_tenant(model_ref, tenant_id)
        if direct is not None:
            return await self._resolution_from_row(direct, required_model_type)
        return None

    async def _resolution_from_row(
        self,
        row: GatewayModel,
        required_model_type: str | None,
    ) -> RegisteredModelResolution | None:
        types = model_types_for_gateway_registration(row.tags or {}, row.capability)
        if required_model_type and required_model_type not in types:
            return None

        cred = await self._creds.get(row.credential_id)
        if cred is None:
            return None

        api_key: str | None = None
        if cred.api_key_encrypted:
            try:
                api_key = decrypt_value(cred.api_key_encrypted, self._encryption_key)
            except Exception:
                return None

        return RegisteredModelResolution(
            virtual_model_name=row.name,
            litellm_model=build_litellm_model_id(row.provider, row.real_model),
            provider=row.provider,
            api_key=api_key,
            api_base=cred.api_base,
            gateway_model_id=row.id,
            is_active=row.enabled,
            last_test_status=row.last_test_status,
            model_types=tuple(types),
        )

    async def resolve_capabilities(
        self,
        model_id: str,
        *,
        billing_team_id: uuid.UUID | None = None,
    ) -> ModelCapabilitySnapshot | None:
        team_id = billing_team_id or resolve_internal_gateway_team_id()
        row = await self._models.resolve_by_name(team_id, model_id)
        if row is None or not row.enabled:
            return None
        return tags_to_capability_snapshot(
            row.tags or {},
            provider=row.provider,
            real_model=row.real_model,
        )

    async def model_features(self, model_id: str) -> frozenset[str] | None:
        snap = await self.resolve_capabilities(model_id)
        if snap is None:
            return None
        return snap.features


def get_model_catalog_adapter(session: AsyncSession) -> ModelCatalogPort:
    return SqlModelCatalogAdapter(session)


__all__ = ["SqlModelCatalogAdapter", "get_model_catalog_adapter"]
