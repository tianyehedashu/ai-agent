"""team_member_reads 单元测试。"""

from __future__ import annotations

from datetime import UTC, datetime
import uuid

import pytest

from domains.identity.application.user_use_case import UserSummary
from domains.tenancy.application.team_member_reads import enrich_team_members
from domains.tenancy.infrastructure.models.team import TeamMember


class _StubUserUseCase:
    async def list_summaries_by_ids(
        self, user_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, UserSummary]:
        return {
            user_ids[0]: UserSummary(
                id=str(user_ids[0]),
                email="member@example.com",
                name="Member Name",
                role="user",
            )
        }


@pytest.mark.unit
@pytest.mark.asyncio
async def test_enrich_team_members_attaches_email_and_name() -> None:
    user_id = uuid.uuid4()
    team_id = uuid.uuid4()
    member = TeamMember(
        id=uuid.uuid4(),
        team_id=team_id,
        user_id=user_id,
        role="member",
        created_at=datetime.now(UTC),
    )

    enriched = await enrich_team_members([member], _StubUserUseCase())  # type: ignore[arg-type]

    assert len(enriched) == 1
    assert enriched[0].user_email == "member@example.com"
    assert enriched[0].user_name == "Member Name"
    assert enriched[0].role == "member"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_enrich_team_members_empty_list() -> None:
    enriched = await enrich_team_members([], _StubUserUseCase())  # type: ignore[arg-type]
    assert enriched == []
