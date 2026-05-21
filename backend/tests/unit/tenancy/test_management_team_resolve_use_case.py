"""管理面团队解析：路径 team_id 优先于 X-Team-Id。"""

from __future__ import annotations

import pytest

from domains.tenancy.application.management_team_resolve_use_case import (
    TenancyManagementTeamResolveUseCase,
)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_path_team_id_wins_over_x_team_id(db_session, test_user) -> None:
    from domains.tenancy.application.team_service import TeamService

    teams = TeamService(db_session)
    personal = await teams.ensure_personal_team(test_user.id)
    shared = await teams.create_team(name="Path Priority Team", owner_user_id=test_user.id)
    await db_session.commit()

    resolver = TenancyManagementTeamResolveUseCase(db_session)
    resolved = await resolver.resolve_management_team(
        user_id=test_user.id,
        platform_user_role="user",
        x_team_id=str(personal.id),
        path_team_id=str(shared.id),
    )
    assert resolved.team_id == shared.id


@pytest.mark.unit
@pytest.mark.asyncio
async def test_x_team_id_used_when_path_missing(db_session, test_user) -> None:
    from domains.tenancy.application.team_service import TeamService

    personal = await TeamService(db_session).ensure_personal_team(test_user.id)
    await db_session.commit()

    resolver = TenancyManagementTeamResolveUseCase(db_session)
    resolved = await resolver.resolve_management_team(
        user_id=test_user.id,
        platform_user_role="user",
        x_team_id=str(personal.id),
        path_team_id=None,
    )
    assert resolved.team_id == personal.id
