"""个人资源 grant：应用层 IO 编排（查 grants / 模型，调用 domain 纯函数）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from domains.gateway.domain.visibility.resource_grant_visibility import (
    GrantedModelSnapshot,
    visible_granted_model_ids,
)
from domains.gateway.infrastructure.models.gateway_model import GatewayModel
from domains.gateway.infrastructure.models.resource_grant import GatewayResourceGrant
from domains.gateway.infrastructure.repositories.resource_grant_repository import (
    GatewayResourceGrantRepository,
)
from domains.tenancy.infrastructure.models.team import Team

from .resource_grants_cache import (
    ResourceGrantCacheEntry,
    get_cached_resource_grants,
    put_cached_resource_grants,
)

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


async def _load_owner_personal_slug_rows(
    session: AsyncSession,
    owner_user_ids: set[uuid.UUID],
) -> list[tuple[uuid.UUID, uuid.UUID, str]]:
    if not owner_user_ids:
        return []
    stmt = select(Team.owner_user_id, Team.id, Team.slug).where(
        Team.kind == "personal",
        Team.owner_user_id.in_(owner_user_ids),
    )
    result = await session.execute(stmt)
    return [(row.owner_user_id, row.id, row.slug) for row in result.all()]


async def grant_cache_entry_for_team(
    session: AsyncSession,
    target_team_id: uuid.UUID,
) -> ResourceGrantCacheEntry:
    return await _grant_cache_entry_for_team(session, target_team_id)


async def _grant_cache_entry_for_team(
    session: AsyncSession,
    target_team_id: uuid.UUID,
) -> ResourceGrantCacheEntry:
    cached = await get_cached_resource_grants(target_team_id)
    if cached is not None:
        return cached
    grants = await GatewayResourceGrantRepository(session).list_enabled_for_team(target_team_id)
    owner_ids = {g.owner_user_id for g in grants}
    slug_rows = await _load_owner_personal_slug_rows(session, owner_ids)
    return await put_cached_resource_grants(
        target_team_id,
        grants,
        slug_rows=slug_rows,
    )


async def granted_subject_keys_for_team(
    session: AsyncSession,
    target_team_id: uuid.UUID,
) -> frozenset[tuple[str, uuid.UUID]]:
    entry = await _grant_cache_entry_for_team(session, target_team_id)
    return entry.granted_keys


async def is_credential_granted_to_team(
    session: AsyncSession,
    *,
    credential_id: uuid.UUID,
    target_team_id: uuid.UUID,
) -> bool:
    keys = await granted_subject_keys_for_team(session, target_team_id)
    return ("credential", credential_id) in keys


async def list_granted_personal_models_for_team(
    session: AsyncSession,
    target_team_id: uuid.UUID,
    *,
    only_enabled: bool = True,
) -> list[GatewayModel]:
    """列出授权给目标团队的个人模型行（仍归属 owner personal team）。"""
    entry = await _grant_cache_entry_for_team(session, target_team_id)
    if not entry.granted_keys:
        return []

    personal_team_ids = {team_id for _owner, team_id, _slug in entry.owner_personal_slugs}
    if not personal_team_ids:
        return []

    stmt = select(GatewayModel).where(GatewayModel.tenant_id.in_(personal_team_ids))
    if only_enabled:
        stmt = stmt.where(GatewayModel.enabled.is_(True))
    result = await session.execute(stmt)
    rows = list(result.scalars().all())
    if not rows:
        return []

    snapshots = [
        GrantedModelSnapshot(
            model_id=row.id,
            credential_id=row.credential_id,
            owner_user_id=owner_for_team(entry, row.tenant_id),
            personal_team_id=row.tenant_id,
        )
        for row in rows
        if row.tenant_id is not None
    ]
    allowed = visible_granted_model_ids(snapshots, set(entry.granted_keys))
    return [row for row in rows if row.id in allowed]


def owner_for_team(entry: ResourceGrantCacheEntry, personal_team_id: uuid.UUID) -> uuid.UUID:
    for owner, team_id, _slug in entry.owner_personal_slugs:
        if team_id == personal_team_id:
            return owner
    return personal_team_id  # pragma: no cover — fallback should not happen


async def list_grants_for_owner(
    session: AsyncSession,
    owner_user_id: uuid.UUID,
) -> list[GatewayResourceGrant]:
    return await GatewayResourceGrantRepository(session).list_for_owner(owner_user_id)


__all__ = [
    "grant_cache_entry_for_team",
    "granted_subject_keys_for_team",
    "is_credential_granted_to_team",
    "list_granted_personal_models_for_team",
    "list_grants_for_owner",
    "owner_for_team",
]
