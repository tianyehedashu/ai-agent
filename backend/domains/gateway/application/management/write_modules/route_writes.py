"""Gateway 管理面变更应用服务（写侧分包；对外 API 不变）。"""

from __future__ import annotations

from typing import Any
import uuid

from domains.gateway.application.management.personal_route_callable_reads import (
    build_personal_route_allowed_refs,
)
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
        actor_user_id: uuid.UUID | None = None,
        actor_is_platform_admin: bool = False,
    ) -> None:
        team = await self._teams.get_team(tenant_id)
        refs = [
            name
            for name in (
                *primary_models,
                *fallbacks_general,
                *fallbacks_content_policy,
                *fallbacks_context_window,
            )
            if name
        ]
        if team is not None and team.kind == "personal" and actor_user_id is not None:
            allowed = await build_personal_route_allowed_refs(
                self._session,
                user_id=actor_user_id,
                is_platform_admin=actor_is_platform_admin,
            )
            unknown = sorted({ref for ref in refs if ref not in allowed})
            if unknown:
                raise ValidationError(f"未注册或不可引用的模型别名: {', '.join(unknown)}")
            return

        available = {
            m.name for m in await self._models.list_for_tenant(tenant_id, only_enabled=False)
        }
        unknown_local: list[str] = []
        for name in refs:
            if name not in available:
                unknown_local.append(name)
        if unknown_local:
            unique = sorted(set(unknown_local))
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
        actor_user_id: uuid.UUID | None = None,
        actor_is_platform_admin: bool = False,
    ) -> Any:
        cleaned_virtual = (virtual_model or "").strip()
        if not cleaned_virtual:
            raise ValidationError("虚拟模型名不能为空")
        existing = await self._routes.get_by_virtual_model_for_tenant(tenant_id, cleaned_virtual)
        if existing is not None:
            raise ValidationError(f"虚拟模型名 '{cleaned_virtual}' 在当前工作区已存在路由")
        from domains.gateway.domain.policies.route_grant_access import (
            assert_local_name_free_of_grant_alias,
        )

        assert_local_name_free_of_grant_alias(
            cleaned_virtual,
            grant_alias_in_use=(
                await self._route_grants.get_active_alias(tenant_id, cleaned_virtual) is not None
            ),
            kind="route",
        )
        await self._validate_route_model_names(
            tenant_id,
            primary_models=primary_models,
            fallbacks_general=fallbacks_general,
            fallbacks_content_policy=fallbacks_content_policy,
            fallbacks_context_window=fallbacks_context_window,
            actor_user_id=actor_user_id,
            actor_is_platform_admin=actor_is_platform_admin,
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
            created_by_user_id=actor_user_id,
        )
        await self.reload_litellm_router()
        return row

    async def update_gateway_route(
        self,
        route_id: uuid.UUID,
        *,
        tenant_id: uuid.UUID,
        fields: dict[str, Any],
        actor_user_id: uuid.UUID | None = None,
        actor_is_platform_admin: bool = False,
    ) -> Any:
        repo = self._routes
        existing = await repo.get(route_id)
        if existing is None or (existing.tenant_id is not None and existing.tenant_id != tenant_id):
            raise ManagementEntityNotFoundError("route", str(route_id))
        patch = dict(fields)
        if patch.get("strategy") is not None:
            patch["strategy"] = validate_routing_strategy(patch["strategy"])
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
            actor_user_id=actor_user_id,
            actor_is_platform_admin=actor_is_platform_admin,
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
        # 级联软撤销该路由的全部跨团队共享授权，避免悬空 grant
        await self._cascade_revoke_route_grants(route_id)
        await repo.delete(route_id)
        await self.reload_litellm_router()
