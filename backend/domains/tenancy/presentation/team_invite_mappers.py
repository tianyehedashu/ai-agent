"""团队邀请候选人 presentation 映射。"""

from __future__ import annotations

from domains.identity.application.ports import InviteCandidateRowView
from domains.tenancy.presentation.schemas.teams import (
    TeamInviteCandidateListResponse,
    TeamInviteCandidateResponse,
)
from libs.api.pagination import PaginatedListResponse


def to_invite_candidate_response(row: InviteCandidateRowView) -> TeamInviteCandidateResponse:
    return TeamInviteCandidateResponse(id=row.id, email=row.email, name=row.name)


def to_invite_candidate_list_response(
    page: PaginatedListResponse[InviteCandidateRowView],
) -> TeamInviteCandidateListResponse:
    return TeamInviteCandidateListResponse(
        items=[to_invite_candidate_response(row) for row in page.items],
        total=page.total,
        page=page.page,
        page_size=page.page_size,
        has_next=page.has_next,
        has_prev=page.has_prev,
    )


__all__ = ["to_invite_candidate_list_response", "to_invite_candidate_response"]
