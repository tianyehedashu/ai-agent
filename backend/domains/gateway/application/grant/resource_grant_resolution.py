"""个人资源 grant：按名解析与 slug 消歧。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from domains.gateway.domain.errors import VkeyAmbiguousModelError
from domains.gateway.domain.vkey.virtual_key_team_prefix_policy import resolve_vkey_model_prefix
from domains.gateway.infrastructure.repositories.model_repository import GatewayModelRepository

from .resource_grant_filter import (
    list_granted_personal_models_for_team,
)
from .resource_grants_cache import (
    build_slug_to_personal_team_map,
)

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

    from domains.gateway.infrastructure.models.gateway_model import GatewayModel


async def _slug_map_for_team(session: AsyncSession, team_id: uuid.UUID) -> dict[str, uuid.UUID]:
    from .resource_grant_filter import grant_cache_entry_for_team

    entry = await grant_cache_entry_for_team(session, team_id)
    return build_slug_to_personal_team_map(entry)


async def resolve_granted_model_by_name(
    session: AsyncSession,
    team_id: uuid.UUID,
    name: str,
    *,
    strict_ambiguity: bool = True,
) -> GatewayModel | None:
    """在团队上下文解析授权个人模型；裸名冲突时 strict 抛错。"""
    cleaned = name.strip()
    if not cleaned:
        return None

    if "/" in cleaned:
        slug_map = await _slug_map_for_team(session, team_id)
        dispatch = resolve_vkey_model_prefix(
            bound_team_id=team_id,
            raw_model=cleaned,
            slug_map=slug_map,
            strict=False,
        )
        if dispatch.matched_slug is None:
            return None
        model = await GatewayModelRepository(session).get_by_name(
            dispatch.effective_team_id,
            dispatch.real_model_name,
        )
        if model is None or not model.enabled:
            return None
        granted = await list_granted_personal_models_for_team(session, team_id)
        granted_ids = {row.id for row in granted}
        return model if model.id in granted_ids else None

    granted = await list_granted_personal_models_for_team(session, team_id)
    matches = [row for row in granted if row.name == cleaned]
    if not matches:
        return None
    if len(matches) == 1:
        return matches[0]
    if strict_ambiguity:
        raise VkeyAmbiguousModelError(
            model_name=cleaned,
            team_count=len(matches),
        )
    return matches[0]


__all__ = [
    "resolve_granted_model_by_name",
]
