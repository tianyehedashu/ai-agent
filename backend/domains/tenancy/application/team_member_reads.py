"""团队成员读侧：批量解析成员展示字段（email / name）。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import uuid

from domains.identity.application.user_use_case import UserUseCase
from domains.tenancy.infrastructure.models.team import TeamMember


@dataclass(frozen=True, slots=True)
class EnrichedTeamMember:
    id: uuid.UUID
    team_id: uuid.UUID
    user_id: uuid.UUID
    role: str
    created_at: datetime
    user_email: str | None = None
    user_name: str | None = None


async def enrich_team_members(
    members: list[TeamMember],
    user_service: UserUseCase,
) -> list[EnrichedTeamMember]:
    if not members:
        return []
    summaries = await user_service.list_summaries_by_ids([m.user_id for m in members])
    out: list[EnrichedTeamMember] = []
    for member in members:
        summary = summaries.get(member.user_id)
        out.append(
            EnrichedTeamMember(
                id=member.id,
                team_id=member.team_id,
                user_id=member.user_id,
                role=member.role,
                created_at=member.created_at,
                user_email=summary.email if summary is not None else None,
                user_name=summary.name if summary is not None else None,
            )
        )
    return out


__all__ = ["EnrichedTeamMember", "enrich_team_members"]
