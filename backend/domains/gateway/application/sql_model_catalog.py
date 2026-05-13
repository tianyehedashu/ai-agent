"""ModelCatalogPort 的 Gateway DB 实现。"""

from __future__ import annotations

from typing import Any
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from bootstrap.config_loader import app_config
from domains.agent.application.ports.model_catalog_port import (
    ModelCapabilitySnapshot,
    ModelCatalogPort,
)
from domains.gateway.application.config_catalog_sync import (
    gateway_model_to_selector_item,
    tags_to_capability_snapshot,
)
from domains.gateway.application.internal_bridge_actor import resolve_internal_gateway_team_id
from domains.gateway.infrastructure.models.gateway_model import GatewayModel
from domains.gateway.infrastructure.repositories.model_repository import GatewayModelRepository


class SqlModelCatalogAdapter:
    """以 ``GatewayModel`` 为运行时目录唯一真源；列表不回退 app.toml。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._models = GatewayModelRepository(session)

    async def list_visible_models(
        self,
        *,
        billing_team_id: uuid.UUID | None,
        model_type: str | None,
    ) -> list[dict[str, Any]]:
        rows = await self._models.list_for_team(billing_team_id, only_enabled=True)
        # 仓储已按「团队行先于全局行」排序；同名只保留第一条（团队覆盖全局）
        by_name: dict[str, GatewayModel] = {}
        for row in rows:
            if row.name not in by_name:
                by_name[row.name] = row
        items: list[dict[str, Any]] = []
        for row in sorted(by_name.values(), key=lambda r: r.name):
            item = gateway_model_to_selector_item(row)
            if model_type and model_type not in item["model_types"]:
                continue
            items.append(item)
        return items

    async def resolve_capabilities(self, model_id: str) -> ModelCapabilitySnapshot | None:
        team_id = resolve_internal_gateway_team_id()
        row = await self._models.get_by_name(team_id, model_id)
        if row is None or not row.enabled:
            return None
        return tags_to_capability_snapshot(row.tags or {})

    async def model_features(self, model_id: str) -> frozenset[str] | None:
        snap = await self.resolve_capabilities(model_id)
        if snap is None:
            info = app_config.models.get_model(model_id)
            if info is None:
                return None
            return info.features
        return snap.features


def get_model_catalog_adapter(session: AsyncSession) -> ModelCatalogPort:
    return SqlModelCatalogAdapter(session)


__all__ = ["SqlModelCatalogAdapter", "get_model_catalog_adapter"]
