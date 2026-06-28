"""Gateway 计费/目录上下文：team 解析与 personal 回退。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
import uuid

from domains.tenancy.application.team_service import TeamService
from libs.iam.permission_context import get_permission_context

from .internal_bridge_actor import resolve_internal_gateway_team_id

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class BillingContext:
    team_id: uuid.UUID | None
    user_id: uuid.UUID | None


async def resolve_billing_context(
    session: AsyncSession,
    *,
    user_id: uuid.UUID | None = None,
) -> BillingContext:
    """与 Chat / GatewayBridge 对齐：PermissionContext team 优先，否则回退 personal team。"""
    team_id = resolve_internal_gateway_team_id()
    uid = user_id
    if uid is None:
        ctx = get_permission_context()
        if ctx is not None and isinstance(ctx.user_id, uuid.UUID):
            uid = ctx.user_id
    if team_id is None and uid is not None:
        personal = await TeamService(session).ensure_personal_team(uid)
        team_id = personal.id
    return BillingContext(team_id=team_id, user_id=uid)


__all__ = ["BillingContext", "resolve_billing_context"]
