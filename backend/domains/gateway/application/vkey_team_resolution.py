"""vkey_team_resolution — 跨团队 vkey model 前缀派发（应用层 IO + domain policy）"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING
import uuid

from sqlalchemy import select

from domains.gateway.domain.errors import VkeyAmbiguousModelError
from domains.gateway.domain.vkey_team_prefix_policy import (
    VkeyModelDispatch,
    resolve_vkey_model_prefix,
)
from domains.gateway.infrastructure.models.gateway_model import GatewayModel
from domains.tenancy.infrastructure.models.team import Team
from utils.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from domains.gateway.domain.types import VirtualKeyPrincipal

logger = get_logger(__name__)

GrantTeamSlugRow = tuple[uuid.UUID, str]


async def fetch_grant_team_slug_rows(
    session: AsyncSession,
    granted_team_ids: tuple[uuid.UUID, ...],
) -> list[GrantTeamSlugRow]:
    """查询 grants 集合内仍存在的 team (id, slug) 行。"""
    if not granted_team_ids:
        return []
    stmt = select(Team.id, Team.slug).where(Team.id.in_(granted_team_ids))
    result = await session.execute(stmt)
    return [(row.id, row.slug) for row in result.all()]


def build_slug_by_tenant_id(rows: list[GrantTeamSlugRow]) -> dict[uuid.UUID, str]:
    """tenant_id → slug（列表侧直接使用，无 slug 反查碰撞）。"""
    return {tenant_id: slug for tenant_id, slug in rows}


def build_unique_slug_to_tenant_id(rows: list[GrantTeamSlugRow]) -> dict[str, uuid.UUID]:
    """slug → tenant_id；仅保留 grants 集合内 slug 唯一者（派发前缀 lookup）。"""
    grouped: dict[str, list[uuid.UUID]] = defaultdict(list)
    for tenant_id, slug in rows:
        grouped[slug].append(tenant_id)
    ambiguous = {slug for slug, ids in grouped.items() if len(ids) > 1}
    if ambiguous:
        logger.warning(
            "ambiguous team slugs among vkey grants (excluded from prefix dispatch): %s",
            sorted(ambiguous),
        )
    return {slug: ids[0] for slug, ids in grouped.items() if len(ids) == 1}


async def get_slug_by_tenant_id_map(
    session: AsyncSession,
    granted_team_ids: tuple[uuid.UUID, ...],
) -> dict[uuid.UUID, str]:
    """列表侧：tenant_id → slug。"""
    rows = await fetch_grant_team_slug_rows(session, granted_team_ids)
    return build_slug_by_tenant_id(rows)


async def get_slug_to_tenant_id_map(
    session: AsyncSession,
    granted_team_ids: tuple[uuid.UUID, ...],
) -> dict[str, uuid.UUID]:
    """派发侧：slug → tenant_id（homonym slug 排除，避免静默错派）。"""
    rows = await fetch_grant_team_slug_rows(session, granted_team_ids)
    return build_unique_slug_to_tenant_id(rows)


async def dispatch_vkey_model(
    session: AsyncSession,
    *,
    vkey: VirtualKeyPrincipal,
    raw_model: str,
    strict: bool = False,
) -> VkeyModelDispatch:
    """根据 model 名前缀决定调用落哪个 team（IO：加载 slug 映射后委托 domain policy）。"""
    if vkey.is_system or "/" not in raw_model:
        return resolve_vkey_model_prefix(
            bound_team_id=vkey.team_id,
            raw_model=raw_model,
            slug_map={},
            strict=strict,
        )

    if not vkey.granted_team_ids:
        return resolve_vkey_model_prefix(
            bound_team_id=vkey.team_id,
            raw_model=raw_model,
            slug_map={},
            strict=strict,
        )

    slug_map = await get_slug_to_tenant_id_map(session, vkey.granted_team_ids)
    return resolve_vkey_model_prefix(
        bound_team_id=vkey.team_id,
        raw_model=raw_model,
        slug_map=slug_map,
        strict=strict,
    )


async def count_grant_teams_with_model(
    session: AsyncSession,
    granted_team_ids: tuple[uuid.UUID, ...],
    model_name: str,
) -> int:
    """统计 granted team 集合中有多少 team 注册了同名 enabled 模型。"""
    if not granted_team_ids or not model_name.strip():
        return 0
    stmt = (
        select(GatewayModel.tenant_id)
        .where(
            GatewayModel.tenant_id.in_(granted_team_ids),
            GatewayModel.name == model_name,
            GatewayModel.enabled.is_(True),
        )
        .distinct()
    )
    result = await session.execute(stmt)
    return len(result.all())


async def assert_vkey_model_not_ambiguous(
    session: AsyncSession,
    *,
    vkey: VirtualKeyPrincipal,
    dispatch: VkeyModelDispatch,
    strict: bool,
) -> None:
    """无前缀 + 多 grant 同名模型：非 strict 记指标；strict 记指标并拒绝。"""
    if vkey.is_system or dispatch.matched_slug is not None:
        return
    if len(vkey.granted_team_ids) <= 1:
        return

    team_count = await count_grant_teams_with_model(
        session, vkey.granted_team_ids, dispatch.real_model_name
    )
    if team_count < 2:
        return

    from domains.gateway.application.gateway_vkey_metrics import (
        record_ambiguous_model_invocation,
    )

    record_ambiguous_model_invocation(
        vkey_id=vkey.vkey_id,
        model_name=dispatch.real_model_name,
    )
    if strict:
        raise VkeyAmbiguousModelError(dispatch.real_model_name, team_count)


__all__ = [
    "GrantTeamSlugRow",
    "VkeyModelDispatch",
    "assert_vkey_model_not_ambiguous",
    "build_slug_by_tenant_id",
    "build_unique_slug_to_tenant_id",
    "count_grant_teams_with_model",
    "dispatch_vkey_model",
    "fetch_grant_team_slug_rows",
    "get_slug_by_tenant_id_map",
    "get_slug_to_tenant_id_map",
]
