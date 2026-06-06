"""Gateway 管理面变更应用服务（写侧分包；对外 API 不变）。"""

from __future__ import annotations

from typing import Any
import uuid

from domains.gateway.application.routing_strategy_validation import validate_routing_strategy
from domains.gateway.domain.errors import (
    ManagementEntityNotFoundError,
)
from libs.exceptions import ValidationError
from utils.logging import get_logger

logger = get_logger(__name__)


class RouteWritesMixin:
    """写侧 mixin — 由 GatewayManagementWriteService 组合。"""

    async def _validate_route_model_names(
        self,
        tenant_id: uuid.UUID,
        *,
        primary_models: list[str],
        fallbacks_general: list[str],
        fallbacks_content_policy: list[str],
        fallbacks_context_window: list[str],
    ) -> None:
        available = {
            m.name for m in await self._models.list_for_tenant(tenant_id, only_enabled=False)
        }
        unknown: list[str] = []
        for name in (
            *primary_models,
            *fallbacks_general,
            *fallbacks_content_policy,
            *fallbacks_context_window,
        ):
            if name and name not in available:
                unknown.append(name)
        if unknown:
            unique = sorted(set(unknown))
            raise ValidationError(f"未注册的模型别名: {', '.join(unique)}")

    async def create_gateway_route(
        self,
        *,
        tenant_id: uuid.UUID,
        virtual_model: str,
        primary_models: list[str],
        fallbacks_general: list[str],
        fallbacks_content_policy: list[str],
        fallbacks_context_window: list[str],
        strategy: str,
        retry_policy: dict[str, Any],
    ) -> Any:
        cleaned_virtual = (virtual_model or "").strip()
        if not cleaned_virtual:
            raise ValidationError("虚拟模型名不能为空")
        existing = await self._routes.get_by_virtual_model_for_tenant(
            tenant_id, cleaned_virtual
        )
        if existing is not None:
            raise ValidationError(
                f"虚拟模型名 '{cleaned_virtual}' 在当前工作区已存在路由"
            )
        await self._validate_route_model_names(
            tenant_id,
            primary_models=primary_models,
            fallbacks_general=fallbacks_general,
            fallbacks_content_policy=fallbacks_content_policy,
            fallbacks_context_window=fallbacks_context_window,
        )
        row = await self._routes.create(
            tenant_id=tenant_id,
            virtual_model=cleaned_virtual,
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
        self, route_id: uuid.UUID, *, tenant_id: uuid.UUID, fields: dict[str, Any]
    ) -> Any:
        repo = self._routes
        existing = await repo.get(route_id)
        if existing is None or (existing.tenant_id is not None and existing.tenant_id != tenant_id):
            raise ManagementEntityNotFoundError("route", str(route_id))
        patch = dict(fields)
        if patch.get("strategy") is not None:
            patch["strategy"] = validate_routing_strategy(str(patch["strategy"]))
        primary_models = patch.get("primary_models", existing.primary_models) or []
        fallbacks_general = patch.get("fallbacks_general", existing.fallbacks_general) or []
        fallbacks_content_policy = (
            patch.get("fallbacks_content_policy", existing.fallbacks_content_policy) or []
        )
        fallbacks_context_window = (
            patch.get("fallbacks_context_window", existing.fallbacks_context_window) or []
        )
        await self._validate_route_model_names(
            tenant_id,
            primary_models=list(primary_models),
            fallbacks_general=list(fallbacks_general),
            fallbacks_content_policy=list(fallbacks_content_policy),
            fallbacks_context_window=list(fallbacks_context_window),
        )
        updated = await repo.update(route_id, **patch)
        if updated is None:
            raise ManagementEntityNotFoundError("route", str(route_id))
        await self.reload_litellm_router()
        return updated

    async def delete_gateway_route(self, route_id: uuid.UUID, *, tenant_id: uuid.UUID) -> None:
        repo = self._routes
        existing = await repo.get(route_id)
        if existing is None or (existing.tenant_id is not None and existing.tenant_id != tenant_id):
            raise ManagementEntityNotFoundError("route", str(route_id))
        await repo.delete(route_id)
        await self.reload_litellm_router()
