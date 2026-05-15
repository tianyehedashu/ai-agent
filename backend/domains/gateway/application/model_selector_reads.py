"""模型选择器读侧：系统目录 + personal gateway_models（Gateway HTTP 与 Agent 解析共用）。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
import uuid

from bootstrap.config import settings
from domains.gateway.application.internal_bridge_actor import resolve_internal_gateway_team_id

if TYPE_CHECKING:
    from domains.agent.application.ports.model_catalog_port import ModelCatalogPort


async def list_available_system_models(
    catalog: ModelCatalogPort,
    *,
    model_type: str | None = None,
    provider: str | None = None,
) -> list[dict[str, Any]]:
    team_id = resolve_internal_gateway_team_id()
    items = await catalog.list_visible_models(
        billing_team_id=team_id,
        model_type=model_type,
    )
    if provider is None:
        return items
    return [m for m in items if str(m.get("provider") or "") == provider]


async def list_personal_models_for_selector(
    catalog: ModelCatalogPort,
    user_id: uuid.UUID,
    *,
    model_type: str | None = None,
    provider: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    items = await catalog.list_personal_models_for_selector(
        user_id,
        model_type,
        provider,
    )
    return items[:limit]


async def get_default_for_model_type(
    catalog: ModelCatalogPort,
    model_type: str,
) -> dict[str, str] | None:
    team_id = resolve_internal_gateway_team_id()
    if model_type == "image":
        model_id = settings.vision_model
        items = await catalog.list_visible_models(
            billing_team_id=team_id,
            model_type="image",
        )
        for m in items:
            if m["id"] == model_id:
                return {"id": model_id, "display_name": str(m["display_name"])}
        return {"id": model_id, "display_name": model_id}
    if model_type == "image_gen":
        available = await catalog.list_visible_models(
            billing_team_id=team_id,
            model_type="image_gen",
        )
        if available:
            return {"id": available[0]["id"], "display_name": available[0]["display_name"]}
        return None
    model_id = settings.default_model
    items = await catalog.list_visible_models(
        billing_team_id=team_id,
        model_type="text",
    )
    for m in items:
        if m["id"] == model_id:
            return {"id": model_id, "display_name": str(m["display_name"])}
    return {"id": model_id, "display_name": model_id}


async def list_available_models(
    catalog: ModelCatalogPort,
    *,
    model_type: str | None = None,
    user_id: uuid.UUID | None = None,
    provider: str | None = None,
) -> dict[str, Any]:
    system_models = await list_available_system_models(
        catalog,
        model_type=model_type,
        provider=provider,
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
