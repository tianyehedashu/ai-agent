"""模型选择器读侧：系统目录 + personal gateway_models（Gateway HTTP 与 Agent 解析共用）。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
import uuid

from domains.gateway.application.bridge.internal_bridge_actor import (
    resolve_internal_gateway_team_id,
)
from domains.gateway.application.quota.entitlement_model_status import (
    annotate_items_entitlement_status,
)

from .scenario_defaults import resolve_scenario_default

if TYPE_CHECKING:
    from domains.gateway.application.model_catalog_port import ModelCatalogPort
    from domains.gateway.application.quota.entitlement_guard import EntitlementGuard


def _resolve_billing_team_id(billing_team_id: uuid.UUID | None) -> uuid.UUID | None:
    """与 ``scenario_defaults`` / ``chat_model_resolution`` 一致：未显式传团队时回退权限上下文团队。"""
    if billing_team_id is not None:
        return billing_team_id
    return resolve_internal_gateway_team_id()


async def list_available_system_models(
    catalog: ModelCatalogPort,
    *,
    model_type: str | None = None,
    provider: str | None = None,
    billing_team_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    entitlement_guard: EntitlementGuard | None = None,
    entitlement_scope: str | None = None,
    entitlement_scope_id: uuid.UUID | None = None,
) -> list[dict[str, Any]]:
    team_id = _resolve_billing_team_id(billing_team_id)
    items = await catalog.list_visible_models(
        billing_team_id=team_id,
        model_type=model_type,
        user_id=user_id,
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
    for m in items:
        if m.get("name") == picked_id:
            return {"id": picked_id, "display_name": str(m.get("display_name") or m.get("name"))}
    return {"id": picked_id, "display_name": picked_id}


async def get_default_for_model_type(
    catalog: ModelCatalogPort,
    model_type: str,
    *,
    billing_team_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
) -> dict[str, str] | None:
    team_id = _resolve_billing_team_id(billing_team_id)
    if model_type == "image":
        items = await catalog.list_visible_models(
            billing_team_id=team_id,
            model_type="image",
            user_id=user_id,
        )
        personal: list[dict[str, Any]] = []
        if user_id is not None:
            personal = await catalog.list_personal_models_for_selector(user_id, "image", None)
        picked = await resolve_scenario_default(
            catalog,
            scenario="vision",
            billing_team_id=team_id,
            user_id=user_id,
        )
        return _default_entry([*items, *personal], picked)
    if model_type == "image_gen":
        available = await catalog.list_visible_models(
            billing_team_id=team_id,
            model_type="image_gen",
            user_id=user_id,
        )
        if not available and user_id is not None:
            personal = await catalog.list_personal_models_for_selector(
                user_id, "image_gen", None
            )
            if personal:
                first = personal[0]
                return {
                    "id": str(first["id"]),
                    "display_name": str(first.get("display_name") or first.get("name")),
                }
        if not available:
            return None
        first = available[0]
        return {"id": str(first["id"]), "display_name": str(first["display_name"])}
    items = await catalog.list_visible_models(
        billing_team_id=team_id,
        model_type="text",
        user_id=user_id,
    )
    personal_items: list[dict[str, Any]] = []
    if user_id is not None:
        personal_items = await catalog.list_personal_models_for_selector(user_id, "text", None)
    picked = await resolve_scenario_default(
        catalog,
        scenario="default",
        billing_team_id=team_id,
        user_id=user_id,
    )
    return _default_entry([*items, *personal_items], picked)


async def list_available_models(
    catalog: ModelCatalogPort,
    *,
    model_type: str | None = None,
    user_id: uuid.UUID | None = None,
    provider: str | None = None,
    billing_team_id: uuid.UUID | None = None,
    entitlement_guard: EntitlementGuard | None = None,
    entitlement_scope: str | None = None,
    entitlement_scope_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    system_models = await list_available_system_models(
        catalog,
        model_type=model_type,
        provider=provider,
        billing_team_id=billing_team_id,
        user_id=user_id,
        entitlement_guard=entitlement_guard,
        entitlement_scope=entitlement_scope,
        entitlement_scope_id=entitlement_scope_id,
    )
    default_for_text = await get_default_for_model_type(
        catalog, "text", billing_team_id=billing_team_id, user_id=user_id
    )
    default_for_vision = await get_default_for_model_type(
        catalog, "image", billing_team_id=billing_team_id, user_id=user_id
    )
    default_for_image_gen = await get_default_for_model_type(
        catalog, "image_gen", billing_team_id=billing_team_id, user_id=user_id
    )
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
