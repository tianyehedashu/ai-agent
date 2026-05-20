"""Gateway 管理面变更应用服务（写侧分包；对外 API 不变）。"""

from __future__ import annotations

from typing import Any
import uuid

from domains.gateway.application.routing_strategy_validation import validate_routing_strategy
from domains.gateway.domain.errors import (
    ManagementEntityNotFoundError,
)
from utils.logging import get_logger

logger = get_logger(__name__)



class RouteWritesMixin:
    """写侧 mixin — 由 GatewayManagementWriteService 组合。"""

    async def create_gateway_route(self, *, tenant_id: uuid.UUID, virtual_model: str, primary_models: list[str], fallbacks_general: list[str], fallbacks_content_policy: list[str], fallbacks_context_window: list[str], strategy: str, retry_policy: dict[str, Any]) -> Any:
        row = await self._routes.create(tenant_id=tenant_id, virtual_model=virtual_model, primary_models=primary_models, fallbacks_general=fallbacks_general, fallbacks_content_policy=fallbacks_content_policy, fallbacks_context_window=fallbacks_context_window, strategy=validate_routing_strategy(strategy), retry_policy=retry_policy)
        await self.reload_litellm_router()
        return row

    async def update_gateway_route(self, route_id: uuid.UUID, *, tenant_id: uuid.UUID, fields: dict[str, Any]) -> Any:
        repo = self._routes
        existing = await repo.get(route_id)
        if existing is None or (existing.tenant_id is not None and existing.tenant_id != tenant_id):
            raise ManagementEntityNotFoundError('route', str(route_id))
        patch = dict(fields)
        if patch.get('strategy') is not None:
            patch['strategy'] = validate_routing_strategy(str(patch['strategy']))
        updated = await repo.update(route_id, **patch)
        if updated is None:
            raise ManagementEntityNotFoundError('route', str(route_id))
        await self.reload_litellm_router()
        return updated

    async def delete_gateway_route(self, route_id: uuid.UUID, *, tenant_id: uuid.UUID) -> None:
        repo = self._routes
        existing = await repo.get(route_id)
        if existing is None or (existing.tenant_id is not None and existing.tenant_id != tenant_id):
            raise ManagementEntityNotFoundError('route', str(route_id))
        await repo.delete(route_id)
        await self.reload_litellm_router()
