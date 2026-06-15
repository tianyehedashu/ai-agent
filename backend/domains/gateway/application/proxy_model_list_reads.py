"""代理端 GET /v1/models 列表组装（OpenAI 形状 + gateway 扩展元数据）。"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
import uuid

from domains.gateway.application.config_catalog_sync import (
    model_types_for_gateway_registration,
    selector_capabilities_from_tags,
)
from domains.gateway.application.entitlement_model_status import (
    compute_model_callable,
    connectivity_status_from_last_test,
    entitlement_status_by_model_names,
)
from domains.gateway.application.gateway_model_listing import GatewayRegistryModelRow
from domains.gateway.domain.types import EntitlementListStatus, ModelConnectivityStatus

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from domains.gateway.infrastructure.models.gateway_model import GatewayModel
    from domains.gateway.infrastructure.models.gateway_route import GatewayRoute
    from domains.gateway.infrastructure.models.system_gateway import SystemGatewayRoute


def _iso_or_none(when: datetime | None) -> str | None:
    if when is None:
        return None
    return when.isoformat()


def build_openai_model_list_item(
    row: GatewayRegistryModelRow,
    *,
    entitlement_status: EntitlementListStatus,
    list_id: str | None = None,
    team_slug: str | None = None,
    include_extended_gateway_metadata: bool = False,
    credential_profile_id: str | None = None,
) -> dict[str, object]:
    """单条 OpenAI Model 对象 + ``model_types`` + ``gateway`` 命名空间。"""
    tags = row.tags or {}
    connectivity = connectivity_status_from_last_test(row.last_test_status)
    effective_list_id = list_id if list_id is not None else row.name
    gateway_meta: dict[str, object] = {
        "display_name": str(tags.get("display_name") or row.name),
        "real_model": row.real_model,
        "connectivity_status": connectivity,
        "connectivity_tested_at": _iso_or_none(row.last_tested_at),
        "connectivity_reason": row.last_test_reason,
        "entitlement_status": entitlement_status,
        "callable": compute_model_callable(
            connectivity_status=connectivity,
            entitlement_status=entitlement_status,
        ),
        "selector_capabilities": selector_capabilities_from_tags(
            tags,
            provider=row.provider,
            real_model=row.real_model,
            credential_profile_id=credential_profile_id,
        ),
    }
    if include_extended_gateway_metadata or team_slug is not None or effective_list_id != row.name:
        gateway_meta["registry_name"] = row.name
    if team_slug is not None:
        gateway_meta["team_slug"] = team_slug
    return {
        "id": effective_list_id,
        "object": "model",
        "created": int(row.created_at.timestamp()),
        "owned_by": row.provider,
        "capability": row.capability,
        "model_types": model_types_for_gateway_registration(tags, row.capability),
        "gateway": gateway_meta,
    }


def _aggregate_connectivity(models: list[GatewayRegistryModelRow]) -> ModelConnectivityStatus | None:
    """路由级连通性聚合：任一 success 即 success；全 failed 即 failed。"""
    statuses = {connectivity_status_from_last_test(m.last_test_status) for m in models}
    if "success" in statuses:
        return "success"
    if "failed" in statuses:
        return "failed"
    return None


def _aggregate_entitlement(
    models: list[GatewayRegistryModelRow],
    entitlement_by_name: dict[str, EntitlementListStatus],
) -> EntitlementListStatus:
    """路由级套餐聚合：任一 active 即 active；优先级 resetting > exhausted > expired > none。"""
    statuses = {entitlement_by_name.get(m.name, "none") for m in models}
    if "active" in statuses:
        return "active"
    if "resetting" in statuses:
        return "resetting"
    if "exhausted" in statuses:
        return "exhausted"
    if "expired" in statuses:
        return "expired"
    return "none"


def _build_route_model_list_item(
    route: GatewayRoute | SystemGatewayRoute,
    models_by_name: dict[str, GatewayRegistryModelRow],
    entitlement_by_name: dict[str, EntitlementListStatus],
    *,
    list_id: str | None = None,
    team_slug: str | None = None,
    include_extended_gateway_metadata: bool = False,
    credential_profiles: dict[uuid.UUID, str] | None = None,
) -> dict[str, object] | None:
    """从 GatewayRoute 构建 OpenAI 格式的模型列表项。

    使用 route 下第一个可部署的 primary_model 的元数据作为基础；
    entitlement 和 connectivity 按"任一可用即可用"聚合。
    """
    primary = list(route.primary_models or ())
    if not primary:
        return None

    resolved_models: list[GatewayRegistryModelRow] = []
    for name in primary:
        m = models_by_name.get(name)
        if m is not None:
            resolved_models.append(m)

    if not resolved_models:
        return None

    base = resolved_models[0]
    tags = base.tags or {}
    connectivity = _aggregate_connectivity(resolved_models)
    entitlement = _aggregate_entitlement(resolved_models, entitlement_by_name)
    latest_tested_at: datetime | None = None
    for m in resolved_models:
        if m.last_tested_at is not None and (
            latest_tested_at is None or m.last_tested_at > latest_tested_at
        ):
            latest_tested_at = m.last_tested_at

    registry_name = route.virtual_model
    effective_list_id = list_id if list_id is not None else route.virtual_model
    profile_id = (
        credential_profiles.get(base.credential_id) if credential_profiles is not None else None
    )
    gateway_meta: dict[str, object] = {
        "display_name": route.virtual_model,
        "real_model": base.real_model,
        "connectivity_status": connectivity,
        "connectivity_tested_at": _iso_or_none(latest_tested_at),
        "connectivity_reason": None,
        "entitlement_status": entitlement,
        "callable": compute_model_callable(
            connectivity_status=connectivity,
            entitlement_status=entitlement,
        ),
        "selector_capabilities": selector_capabilities_from_tags(
            tags,
            provider=base.provider,
            real_model=base.real_model,
            credential_profile_id=profile_id,
        ),
    }
    if (
        include_extended_gateway_metadata
        or team_slug is not None
        or effective_list_id != route.virtual_model
    ):
        gateway_meta["registry_name"] = registry_name
    if team_slug is not None:
        gateway_meta["team_slug"] = team_slug

    return {
        "id": effective_list_id,
        "object": "model",
        "created": int(base.created_at.timestamp()),
        "owned_by": base.provider,
        "capability": base.capability,
        "model_types": model_types_for_gateway_registration(tags, base.capability),
        "gateway": gateway_meta,
    }


async def build_proxy_models_list(
    session: AsyncSession,
    models: list[GatewayRegistryModelRow],
    *,
    routes: list[GatewayRoute | SystemGatewayRoute] | None = None,
    entitlement_scope: str | None,
    entitlement_scope_id: uuid.UUID | None,
    route_lookup_models: list[GatewayRegistryModelRow] | None = None,
    model_list_ids: list[str] | None = None,
    model_team_slugs: list[str | None] | None = None,
    route_list_ids: list[str] | None = None,
    route_team_slugs: list[str | None] | None = None,
    route_lookup_pools: list[list[GatewayRegistryModelRow]] | None = None,
    include_extended_gateway_metadata: bool = False,
) -> list[dict[str, object]]:
    """批量注入 entitlement 状态并组装代理模型列表（含 Route virtual_model）。

    ``route_lookup_models`` 用于解析 route 的 primary_models 元数据，
    可与 ``models`` 分离（例如 ``models`` 已按 allowed_models 过滤，
    但 route 解析仍需完整模型池）。
    """
    if not models and not routes:
        return []

    if model_list_ids is not None and len(model_list_ids) != len(models):
        msg = "model_list_ids length must match models"
        raise ValueError(msg)
    if model_team_slugs is not None and len(model_team_slugs) != len(models):
        msg = "model_team_slugs length must match models"
        raise ValueError(msg)
    if routes:
        route_count = len(routes)
        if route_list_ids is not None and len(route_list_ids) != route_count:
            msg = "route_list_ids length must match routes"
            raise ValueError(msg)
        if route_team_slugs is not None and len(route_team_slugs) != route_count:
            msg = "route_team_slugs length must match routes"
            raise ValueError(msg)
        if route_lookup_pools is not None and len(route_lookup_pools) != route_count:
            msg = "route_lookup_pools length must match routes"
            raise ValueError(msg)

    names = [m.name for m in models]
    if routes:
        for route in routes:
            names.extend(route.primary_models or ())

    entitlement_by_name = await entitlement_status_by_model_names(
        session,
        scope=entitlement_scope,
        scope_id=entitlement_scope_id,
        model_names=names,
    )

    lookup_pool = route_lookup_models if route_lookup_models is not None else models
    models_by_name = {m.name: m for m in lookup_pool}
    from domains.gateway.application.model_credential_enrichment import (
        build_credential_profile_map_for_models,
    )

    profile_source = [*models, *lookup_pool]
    credential_profiles = await build_credential_profile_map_for_models(session, profile_source)
    result: list[dict[str, object]] = []

    for index, row in enumerate(models):
        list_id = model_list_ids[index] if model_list_ids is not None else None
        team_slug = (
            model_team_slugs[index]
            if model_team_slugs is not None and index < len(model_team_slugs)
            else None
        )
        result.append(
            build_openai_model_list_item(
                row,
                entitlement_status=entitlement_by_name.get(row.name, "none"),
                list_id=list_id,
                team_slug=team_slug,
                include_extended_gateway_metadata=include_extended_gateway_metadata,
                credential_profile_id=credential_profiles.get(row.credential_id),
            )
        )

    if routes:
        for index, route in enumerate(routes):
            list_id = route_list_ids[index] if route_list_ids is not None else None
            team_slug = (
                route_team_slugs[index]
                if route_team_slugs is not None and index < len(route_team_slugs)
                else None
            )
            if route_lookup_pools is not None and index < len(route_lookup_pools):
                route_models_by_name = {m.name: m for m in route_lookup_pools[index]}
            else:
                route_models_by_name = models_by_name
            item = _build_route_model_list_item(
                route,
                route_models_by_name,
                entitlement_by_name,
                list_id=list_id,
                team_slug=team_slug,
                include_extended_gateway_metadata=include_extended_gateway_metadata,
                credential_profiles=credential_profiles,
            )
            if item is not None:
                result.append(item)

    return result


__all__ = [
    "build_openai_model_list_item",
    "build_proxy_models_list",
]
