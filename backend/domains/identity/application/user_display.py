"""跨域用户展示名解析（Gateway 鉴权 / 内部桥接复用）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from domains.identity.application.ports import UserSummaryQueryPort, user_display_label
from domains.identity.application.user_use_case import UserUseCase

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


async def resolve_user_display_snapshot(
    session: AsyncSession,
    user_id: uuid.UUID | None,
    *,
    user_query: UserSummaryQueryPort | None = None,
) -> str | None:
    """按 user_id 解析日志/metadata 用展示名；无 user_id 时返回 None。"""
    if user_id is None:
        return None
    query = user_query if user_query is not None else UserUseCase(session)
    views = await query.list_summary_views_by_ids([user_id])
    return user_display_label(views.get(user_id))


__all__ = ["resolve_user_display_snapshot"]
