"""GatewayBridge 用模型能力解析（编排 SqlModelCatalogAdapter）。"""

from __future__ import annotations

from typing import TYPE_CHECKING
import uuid

from domains.gateway.application.sql_model_catalog import SqlModelCatalogAdapter
from domains.gateway.domain.model_capability import ModelCapabilitySnapshot

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def resolve_capabilities_for_bridge(
    session: AsyncSession,
    *,
    model_id: str,
    billing_team_id: uuid.UUID,
) -> ModelCapabilitySnapshot | None:
    """按团队上下文解析虚拟模型能力快照。"""
    catalog = SqlModelCatalogAdapter(session)
    return await catalog.resolve_capabilities(model_id, billing_team_id=billing_team_id)


__all__ = ["resolve_capabilities_for_bridge"]
