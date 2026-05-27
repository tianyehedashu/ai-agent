"""团队邀请候选人分页读侧（scope 在 tenancy domain；用户查询委托 identity 端口）。"""

from __future__ import annotations

import uuid

from domains.identity.application.ports import (
    InviteCandidateRowView,
    TeamInviteCandidateQueryPort,
)
from domains.tenancy.domain.policies.team_invite_candidate_scope import (
    parse_invite_candidate_scope,
)
from libs.api.pagination import PageParams, PaginatedListResponse


class TeamInviteCandidateReads:
    def __init__(self, invite_query: TeamInviteCandidateQueryPort) -> None:
        self._invite_query = invite_query

    async def list_candidates_page(
        self,
        page: PageParams,
        *,
        team_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        team_settings: dict[str, object] | None,
        search: str | None = None,
    ) -> PaginatedListResponse[InviteCandidateRowView]:
        scope = parse_invite_candidate_scope(team_settings)
        return await self._invite_query.list_team_invite_candidates_page(
            page,
            team_id=team_id,
            actor_user_id=actor_user_id,
            scope=scope,
            search=search,
        )


__all__ = ["TeamInviteCandidateReads"]
