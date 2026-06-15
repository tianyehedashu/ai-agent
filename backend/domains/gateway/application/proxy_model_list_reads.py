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
from domains.gateway.domain.types import EntitlementListStatus, ModelConnectivityStatus
from domains.gateway.infrastructure.models.gateway_model import GatewayModel

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from domains.gateway.infrastructure.models.gateway_route import GatewayRoute
    from domains.gateway.infrastructure.models.system_gateway import SystemGatewayRoute


def _iso_or_none(when: datetime | None) -> str | None:
    if when is None:
        return None
    return when.isoformat()


def build_openai_model_list_item(
    row: GatewayModel,
    *,
    entitlement_status: EntitlementListStatus,
) -> dict[str, object]:
    """单条 OpenAI Model 对象 + ``model_types`` + ``gateway`` 命名空间。"""
    tags = row.tags or {}
    connectivity = connectivity_status_from_last_test(row.last_test_status)
    return {
        "id": row.name,
        "object": "model",
        "created": int(row.created_at.timestamp()),
        "owned_by": row.provider,
        "capability": row.capability,
        "model_types": model_types_for_gateway_registration(tags, row.capability),
        "gateway": {
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
                tags, provider=row.provider, real_model=row.real_model
            ),
        },
    }


def _aggregate_connectivity(models: list[GatewayModel]) -> ModelConnectivityStatus | None:
    """路由级连通性聚合：任一 success 即 success；全 failed 即 failed。"""
    statuses = {connectivity_status_from_last_test(m.last_test_status) for m in models}
    if "success" in statuses:
        return "success"
    if "failed" in statuses:
        return "failed"
    return None


def _aggregate_entitlement(
    models: list[GatewayModel],
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
    models_by_name: dict[str, GatewayModel],
    entitlement_by_name: dict[str, EntitlementListStatus],
) -> dict[str, object] | None:
    """从 GatewayRoute 构建 OpenAI 格式的模型列表项。

    使用 route 下第一个可部署的 primary_model 的元数据作为基础；
    entitlement 和 connectivity 按"任一可用即可用"聚合。
    """
    primary = list(route.primary_models or ())
    if not primary:
        return None

    resolved_models: list[GatewayModel] = []
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

    return {
        "id": route.virtual_model,
        "object": "model",
        "created": int(base.created_at.timestamp()),
        "owned_by": base.provider,
        "capability": base.capability,
        "model_types": model_types_for_gateway_registration(tags, base.capability),
        "gateway": {
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
                tags, provider=base.provider, real_model=base.real_model
            ),
        },
    }


async def build_proxy_models_list(
    session: AsyncSession,
    models: list[GatewayModel],
    *,
    routes: list[GatewayRoute | SystemGatewayRoute] | None = None,
    entitlement_scope: str | None,
    entitlement_scope_id: uuid.UUID | None,
    route_lookup_models: list[GatewayModel] | None = None,
) -> list[dict[str, object]]:
    """批量注入 entitlement 状态并组装代理模型列表（含 Route virtual_model）。

    ``route_lookup_models`` 用于解析 route 的 primary_models 元数据，
    可与 ``models`` 分离（例如 ``models`` 已按 allowed_models 过滤，
    但 route 解析仍需完整模型池）。
    """
    if not models and not routes:
        return []

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
    result: list[dict[str, object]] = []

    for row in models:
        result.append(
            build_openai_model_list_item(
                row,
                entitlement_status=entitlement_by_name.get(row.name, "none"),
            )
        )

    if routes:
        for route in routes:
            item = _build_route_model_list_item(route, models_by_name, entitlement_by_name)
            if item is not None:
                result.append(item)

    return result


__all__ = [
    "build_openai_model_list_item",
    "build_proxy_models_list",
]
