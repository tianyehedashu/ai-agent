"""Tenancy 应用服务单测。"""

import pytest

from domains.tenancy.application.team_service import TeamService
from domains.tenancy.infrastructure.repositories.team_repository import TeamRepository


@pytest.mark.asyncio
async def test_ensure_personal_team_idempotent(db_session, test_user):
    svc = TeamService(db_session)
    team_a = await svc.ensure_personal_team(test_user.id)
    team_b = await svc.ensure_personal_team(test_user.id)
    assert team_a.id == team_b.id


@pytest.mark.asyncio
async def test_team_repository_get_personal(db_session, test_user):
    await TeamService(db_session).ensure_personal_team(test_user.id)
    t = await TeamRepository(db_session).get_personal(test_user.id)
    assert t is not None
    assert t.kind == "personal"


@pytest.mark.asyncio
async def test_list_teams_with_roles_for_user(db_session, test_user):
    svc = TeamService(db_session)
    await svc.ensure_personal_team(test_user.id)
    items = await svc.list_teams_with_roles_for_user(test_user.id)
    assert len(items) >= 1
    team, role = items[0]
    assert team.owner_user_id == test_user.id
    assert role == "owner"
