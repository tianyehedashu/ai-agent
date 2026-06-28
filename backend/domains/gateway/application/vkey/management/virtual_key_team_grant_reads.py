"""virtual_key_team_grant_reads — 跨团队授权读服务"""

from __future__ import annotations

from typing import TYPE_CHECKING
import uuid

from sqlalchemy import select

from domains.gateway.infrastructure.models.virtual_key_team_grant import (
    GatewayVirtualKeyTeamGrant,
)
from domains.gateway.infrastructure.repositories.virtual_key_team_grant_repository import (
    VirtualKeyTeamGrantRepository,
)
from domains.gateway.presentation.schemas.grants import (
    GrantableTeamResponse,
    VirtualKeyTeamGrantResponse,
)

from .virtual_key_team_grant_read_mappers import (
    grantable_teams_to_responses,
    grants_to_responses,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession


async def list_active_grants_for_vkey(
    session: AsyncSession, vkey_id: uuid.UUID
) -> list[GatewayVirtualKeyTeamGrant]:
    """返回该 vkey 的所有 active grant 行（含自洽行）。"""
    repo = VirtualKeyTeamGrantRepository(session)
    return await repo.list_active_for_vkey(vkey_id)


async def list_active_grant_tenant_ids(
    session: AsyncSession, vkey_id: uuid.UUID
) -> tuple[uuid.UUID, ...]:
    """鉴权热路径：返回该 vkey 所有 active grant 的 tenant_id。"""
    repo = VirtualKeyTeamGrantRepository(session)
    return await repo.list_active_tenant_ids(vkey_id)


async def fetch_team_display_by_tenant_ids(
    session: AsyncSession,
    tenant_ids: list[uuid.UUID],
) -> dict[uuid.UUID, tuple[str, str]]:
    """批量拉取 team (name, slug)。"""
    if not tenant_ids:
        return {}
    from domains.tenancy.infrastructure.models.team import Team

    stmt = select(Team.id, Team.name, Team.slug).where(Team.id.in_(tenant_ids))
    result = await session.execute(stmt)
    return {row.id: (row.name, row.slug) for row in result.all()}


async def fetch_model_metadata_for_tenants(
    session: AsyncSession,
    tenant_ids: list[uuid.UUID],
) -> tuple[dict[uuid.UUID, int], dict[uuid.UUID, list[str]]]:
    """批量拉取 team 模型数与模型名列表（grants UI 用）。"""
    if not tenant_ids:
        return {}, {}
    from domains.gateway.infrastructure.repositories.model_repository import (
        GatewayModelRepository,
    )

    repo = GatewayModelRepository(session)
    counts = await repo.count_enabled_grouped_by_tenant(tenant_ids)
    names = await repo.list_enabled_names_grouped_by_tenant(tenant_ids)
    return counts, names


async def map_grants_to_responses(
    session: AsyncSession,
    grants: Sequence[GatewayVirtualKeyTeamGrant],
) -> list[VirtualKeyTeamGrantResponse]:
    """ORM grant 行 → API Schema（含 team 展示字段与模型元数据）。"""
    tenant_ids = [g.tenant_id for g in grants]
    team_map = await fetch_team_display_by_tenant_ids(session, tenant_ids)
    model_counts, model_names = await fetch_model_metadata_for_tenants(session, tenant_ids)
    return grants_to_responses(
        grants,
        team_map=team_map,
        model_counts=model_counts,
        model_names=model_names,
    )


async def list_grantable_teams_for_actor(
    session: AsyncSession,
    *,
    actor_user_id: uuid.UUID,
    vkey_tenant_id: uuid.UUID,
    existing_grant_tenant_ids: set[uuid.UUID],
) -> list[tuple[uuid.UUID, str, str]]:
    """返回 actor 可作 grant 目标的 team（membership ∖ 已授权 ∖ 主属）。

    Returns:
        list[(team_id, name, slug)]
    """
    from domains.tenancy.infrastructure.models.team import Team, TeamMember

    stmt = (
        select(Team.id, Team.name, Team.slug)
        .join(TeamMember, TeamMember.team_id == Team.id)
        .where(
            TeamMember.user_id == actor_user_id,
            Team.is_active.is_(True),
            Team.id != vkey_tenant_id,
            ~Team.id.in_(existing_grant_tenant_ids),
        )
    )
    result = await session.execute(stmt)
    return [(row.id, row.name, row.slug) for row in result.all()]


async def list_grantable_team_responses(
    session: AsyncSession,
    *,
    actor_user_id: uuid.UUID,
    vkey_tenant_id: uuid.UUID,
    existing_grant_tenant_ids: set[uuid.UUID],
) -> list[GrantableTeamResponse]:
    """可授权 team 列表 → API Schema。"""
    rows = await list_grantable_teams_for_actor(
        session,
        actor_user_id=actor_user_id,
        vkey_tenant_id=vkey_tenant_id,
        existing_grant_tenant_ids=existing_grant_tenant_ids,
    )
    tenant_ids = [team_id for team_id, _name, _slug in rows]
    model_counts, _names = await fetch_model_metadata_for_tenants(session, tenant_ids)
    return grantable_teams_to_responses(rows, model_counts=model_counts)


__all__ = [
    "fetch_model_metadata_for_tenants",
    "fetch_team_display_by_tenant_ids",
    "list_active_grant_tenant_ids",
    "list_active_grants_for_vkey",
    "list_grantable_team_responses",
    "list_grantable_teams_for_actor",
    "map_grants_to_responses",
]
