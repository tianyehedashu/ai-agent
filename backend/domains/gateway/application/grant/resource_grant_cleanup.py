"""Resource grant 写路径清理（删凭据/模型时级联）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from domains.gateway.application.observability.gateway_cache_invalidation import (
    invalidate_gateway_resource_grants_cache_for_team,
)
from domains.gateway.infrastructure.repositories.resource_grant_repository import (
    GatewayResourceGrantRepository,
)

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


async def purge_resource_grants_for_subjects(
    session: AsyncSession,
    *,
    subjects: list[tuple[str, list[uuid.UUID]]],
) -> None:
    """删除指定 subject 的全部 grant，并失效受影响团队的 resource grant 读缓存。"""
    repo = GatewayResourceGrantRepository(session)
    target_team_ids: set[uuid.UUID] = set()
    for subject_kind, subject_ids in subjects:
        if not subject_ids:
            continue
        for subject_id in subject_ids:
            for grant in await repo.list_for_subject(subject_kind, subject_id):
                target_team_ids.add(grant.target_team_id)
        await repo.delete_by_subject_ids(subject_kind, subject_ids)
    for team_id in target_team_ids:
        await invalidate_gateway_resource_grants_cache_for_team(team_id)


__all__ = ["purge_resource_grants_for_subjects"]
