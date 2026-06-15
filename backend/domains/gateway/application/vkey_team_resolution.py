"""vkey_team_resolution — 跨团队 vkey model 前缀派发（应用层 IO + domain policy）"""

from __future__ import annotations

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

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from domains.gateway.domain.types import VirtualKeyPrincipal


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

    slug_map = await _get_slug_to_tenant_id_map(session, vkey.granted_team_ids)
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
    "VkeyModelDispatch",
    "assert_vkey_model_not_ambiguous",
    "count_grant_teams_with_model",
    "dispatch_vkey_model",
]


async def _get_slug_to_tenant_id_map(
    session: AsyncSession,
    granted_team_ids: tuple[uuid.UUID, ...],
) -> dict[str, uuid.UUID]:
    """查询 grants 集合内 team 的 {slug: tenant_id} 映射。"""
    stmt = select(Team.id, Team.slug).where(Team.id.in_(granted_team_ids))
    result = await session.execute(stmt)
    return {row.slug: row.id for row in result.all()}
