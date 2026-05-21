"""模型选择器读侧：系统目录 + personal gateway_models（Gateway HTTP 与 Agent 解析共用）。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
import uuid

from domains.gateway.application.entitlement_model_status import annotate_items_entitlement_status
from domains.gateway.application.internal_bridge_actor import resolve_internal_gateway_team_id
from domains.gateway.application.scenario_defaults import resolve_scenario_default

if TYPE_CHECKING:
    from domains.gateway.application.entitlement_guard import EntitlementGuard
    from domains.gateway.application.model_catalog_port import ModelCatalogPort


async def list_available_system_models(
    catalog: ModelCatalogPort,
    *,
    model_type: str | None = None,
    provider: str | None = None,
    entitlement_guard: EntitlementGuard | None = None,
    entitlement_scope: str | None = None,
    entitlement_scope_id: uuid.UUID | None = None,
) -> list[dict[str, Any]]:
    team_id = resolve_internal_gateway_team_id()
    items = await catalog.list_visible_models(
        billing_team_id=team_id,
        model_type=model_type,
    )
    if provider is not None:
        items = [m for m in items if str(m.get("provider") or "") == provider]
    return await annotate_items_entitlement_status(
        items,
        guard=entitlement_guard,
        scope=entitlement_scope,
        scope_id=entitlement_scope_id,
    )


async def list_personal_models_for_selector(
    catalog: ModelCatalogPort,
    user_id: uuid.UUID,
    *,
    model_type: str | None = None,
    provider: str | None = None,
    limit: int = 100,
    entitlement_guard: EntitlementGuard | None = None,
    entitlement_scope: str | None = None,
    entitlement_scope_id: uuid.UUID | None = None,
) -> list[dict[str, Any]]:
    items = await catalog.list_personal_models_for_selector(
        user_id,
        model_type,
        provider,
    )
    items = items[:limit]
    return await annotate_items_entitlement_status(
        items,
        guard=entitlement_guard,
        scope=entitlement_scope,
        scope_id=entitlement_scope_id,
    )


def _default_entry(items: list[dict[str, Any]], picked_id: str | None) -> dict[str, str] | None:
    if not picked_id:
        return None
    for m in items:
        if m.get("id") == picked_id:
            return {"id": picked_id, "display_name": str(m["display_name"])}
    return {"id": picked_id, "display_name": picked_id}


async def get_default_for_model_type(
    catalog: ModelCatalogPort,
    model_type: str,
) -> dict[str, str] | None:
    team_id = resolve_internal_gateway_team_id()
    if model_type == "image":
        items = await catalog.list_visible_models(
            billing_team_id=team_id,
            model_type="image",
        )
        picked = await resolve_scenario_default(catalog, scenario="vision")
        return _default_entry(items, picked)
    if model_type == "image_gen":
        available = await catalog.list_visible_models(
            billing_team_id=team_id,
            model_type="image_gen",
        )
        if not available:
            return None
        first = available[0]
        return {"id": str(first["id"]), "display_name": str(first["display_name"])}
    items = await catalog.list_visible_models(
        billing_team_id=team_id,
        model_type="text",
    )
    picked = await resolve_scenario_default(catalog, scenario="default")
    return _default_entry(items, picked)


async def list_available_models(
    catalog: ModelCatalogPort,
    *,
    model_type: str | None = None,
    user_id: uuid.UUID | None = None,
    provider: str | None = None,
    entitlement_guard: EntitlementGuard | None = None,
    entitlement_scope: str | None = None,
    entitlement_scope_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    system_models = await list_available_system_models(
        catalog,
        model_type=model_type,
        provider=provider,
        entitlement_guard=entitlement_guard,
        entitlement_scope=entitlement_scope,
        entitlement_scope_id=entitlement_scope_id,
    )
    default_for_text = await get_default_for_model_type(catalog, "text")
    default_for_vision = await get_default_for_model_type(catalog, "image")
    default_for_image_gen = await get_default_for_model_type(catalog, "image_gen")
    personal_items: list[dict[str, Any]] = []
    if user_id is not None:
        personal_items = await list_personal_models_for_selector(
            catalog,
            user_id,
            model_type=model_type,
            provider=provider,
            entitlement_guard=entitlement_guard,
            entitlement_scope=entitlement_scope,
            entitlement_scope_id=entitlement_scope_id,
        )
    return {
        "system_models": system_models,
        "user_models": personal_items,
        "default_for_text": default_for_text,
        "default_for_vision": default_for_vision,
        "default_for_image_gen": default_for_image_gen,
    }


__all__ = [
    "get_default_for_model_type",
    "list_available_models",
    "list_available_system_models",
    "list_personal_models_for_selector",
]
