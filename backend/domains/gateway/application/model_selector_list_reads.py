"""模型选择器分页读侧。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
import uuid

from domains.gateway.application.config_catalog_sync import gateway_model_to_selector_item
from domains.gateway.application.entitlement_model_status import annotate_items_entitlement_status
from domains.gateway.application.gateway_model_listing import (
    GatewayRegistryModelRow,
    list_merged_models_for_tenant,
)
from domains.gateway.application.internal_bridge_actor import resolve_internal_gateway_team_id
from domains.gateway.application.model_list_pipeline import (
    ModelListQuery,
    resolved_registry_ability,
)
from domains.gateway.application.model_selector_reads import get_default_for_model_type
from domains.gateway.application.personal_models import gateway_model_to_selector_user_item
from domains.gateway.domain.policies.model_list_policy import (
    ModelListConnectivityFilter,
    matches_connectivity_filter,
    matches_search,
    sort_selector_items,
    summarize_selector_items,
)
from domains.gateway.domain.registry_model_types import selector_item_matches_ability_filter
from domains.gateway.infrastructure.repositories.model_repository import GatewayModelRepository
from domains.tenancy.application.team_service import TeamService
from libs.api.pagination import build_page, slice_page

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from domains.gateway.application.entitlement_guard import EntitlementGuard
    from domains.gateway.application.model_catalog_port import ModelCatalogPort


async def _system_selector_rows(
    session: AsyncSession,
    *,
    billing_team_id: uuid.UUID | None,
    user_id: uuid.UUID | None,
) -> list[GatewayRegistryModelRow]:
    rows = await list_merged_models_for_tenant(
        session,
        billing_team_id,
        only_enabled=True,
        user_id=user_id,
    )
    by_name: dict[str, GatewayRegistryModelRow] = {}
    for row in rows:
        if row.name not in by_name:
            by_name[row.name] = row
    return list(by_name.values())


def _filter_selector_items(
    items: list[dict[str, object]],
    query: ModelListQuery,
) -> list[dict[str, object]]:
    filtered = items
    if query.connectivity != ModelListConnectivityFilter.ALL:
        filtered = [
            item
            for item in filtered
            if matches_connectivity_filter(
                item.get("last_test_status")
                if isinstance(item.get("last_test_status"), str)
                else None,
                query.connectivity,
            )
        ]
    return sort_selector_items(filtered, sort_field=query.sort, order=query.order)


async def list_available_models_page(
    catalog: ModelCatalogPort,
    session: AsyncSession,
    query: ModelListQuery,
    *,
    model_type: str | None = None,
    user_id: uuid.UUID | None = None,
    entitlement_guard: EntitlementGuard | None = None,
    entitlement_scope: str | None = None,
    entitlement_scope_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    team_id = resolve_internal_gateway_team_id()
    system_rows = await _system_selector_rows(
        session,
        billing_team_id=team_id,
        user_id=user_id,
    )
    ability_filter = model_type or resolved_registry_ability(query)
    system_items: list[dict[str, object]] = []
    for row in system_rows:
        item = gateway_model_to_selector_item(row)
        if ability_filter and not selector_item_matches_ability_filter(item, ability_filter):
            continue
        item["enabled"] = row.enabled
        item["last_test_status"] = row.last_test_status
        system_items.append(item)

    if query.provider is not None:
        system_items = [i for i in system_items if str(i.get("provider") or "") == query.provider]
    system_items = [
        i
        for i in system_items
        if matches_search(
            name=str(i.get("display_name") or i.get("id") or ""),
            real_model=str(i.get("real_model") or i.get("model_id") or ""),
            provider=str(i.get("provider") or ""),
            q=query.q,
        )
    ]
    system_items = await annotate_items_entitlement_status(
        system_items,
        guard=entitlement_guard,
        scope=entitlement_scope,
        scope_id=entitlement_scope_id,
    )
    system_sorted = _filter_selector_items(system_items, query)
    system_page_items, system_total = slice_page(
        system_sorted,
        page=query.page_params.page,
        page_size=query.page_params.page_size,
    )

    personal_items: list[dict[str, object]] = []
    if user_id is not None:
        teams = TeamService(session)
        personal_team = await teams.ensure_personal_team(user_id)
        repo = GatewayModelRepository(session)
        personal_rows = await repo.list_tenant_owned(
            personal_team.id,
            only_enabled=True,
            provider=query.provider,
        )
        for row in personal_rows:
            item = gateway_model_to_selector_user_item(row)
            if ability_filter and not selector_item_matches_ability_filter(item, ability_filter):
                continue
            item["enabled"] = row.enabled
            personal_items.append(item)
        personal_items = [
            i
            for i in personal_items
            if matches_search(
                name=str(i.get("name") or ""),
                real_model=str(i.get("model_id") or ""),
                provider=str(i.get("provider") or ""),
                q=query.q,
            )
        ]
        personal_items = await annotate_items_entitlement_status(
            personal_items,
            guard=entitlement_guard,
            scope=entitlement_scope,
            scope_id=entitlement_scope_id,
        )
    personal_sorted = _filter_selector_items(personal_items, query)
    personal_page_items, personal_total = slice_page(
        personal_sorted,
        page=query.page_params.page,
        page_size=query.page_params.page_size,
    )

    default_for_text = await get_default_for_model_type(catalog, "text")
    default_for_vision = await get_default_for_model_type(catalog, "image")
    default_for_image_gen = await get_default_for_model_type(catalog, "image_gen")

    return {
        "system_models": build_page(
            items=system_page_items,
            total=system_total,
            page=query.page_params.page,
            page_size=query.page_params.page_size,
        ).model_dump(),
        "user_models": build_page(
            items=personal_page_items,
            total=personal_total,
            page=query.page_params.page,
            page_size=query.page_params.page_size,
        ).model_dump(),
        "default_for_text": default_for_text,
        "default_for_vision": default_for_vision,
        "default_for_image_gen": default_for_image_gen,
        "connectivity_summary": summarize_selector_items([*system_items, *personal_items]),
    }


__all__ = ["list_available_models_page"]
