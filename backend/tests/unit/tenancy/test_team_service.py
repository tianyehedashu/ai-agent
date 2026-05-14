"""Tenancy 应用服务单测。"""

import uuid

import pytest

from domains.agent.infrastructure.models import agent as _agent_model  # noqa: F401
from domains.identity.infrastructure.models.user import User
from domains.tenancy.application.team_service import TeamService
from domains.tenancy.infrastructure.repositories.team_repository import TeamRepository
from libs.exceptions import TeamNotFoundError


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


@pytest.mark.asyncio
async def test_add_member_personal_team_rejects_non_owner(db_session, test_user):
    other = User(
        email=f"other_{uuid.uuid4()}@example.com",
        hashed_password="x",
        name="Other",
    )
    db_session.add(other)
    await db_session.commit()
    await db_session.refresh(other)

    svc = TeamService(db_session)
    personal = await svc.ensure_personal_team(test_user.id)
    with pytest.raises(ValueError, match="Personal teams cannot have members"):
        await svc.add_member(personal.id, other.id, "member")


@pytest.mark.asyncio
async def test_add_member_personal_team_owner_role_update(db_session, test_user):
    svc = TeamService(db_session)
    personal = await svc.ensure_personal_team(test_user.id)
    row = await svc.add_member(personal.id, test_user.id, "owner")
    assert row.role == "owner"


@pytest.mark.asyncio
async def test_add_member_unknown_team_raises_team_not_found(db_session, test_user):
    svc = TeamService(db_session)
    missing = uuid.uuid4()
    with pytest.raises(TeamNotFoundError):
        await svc.add_member(missing, test_user.id, "member")


@pytest.mark.asyncio
async def test_add_member_rejects_owner_role_for_non_owner_user(db_session, test_user):
    other = User(
        email=f"peer_{uuid.uuid4()}@example.com",
        hashed_password="x",
        name="Peer",
    )
    db_session.add(other)
    await db_session.commit()
    await db_session.refresh(other)

    svc = TeamService(db_session)
    await svc.ensure_personal_team(test_user.id)
    shared = await svc.create_team(name="Shared", owner_user_id=test_user.id)
    with pytest.raises(ValueError, match="Only the team owner may hold"):
        await svc.add_member(shared.id, other.id, "owner")


@pytest.mark.asyncio
async def test_add_member_shared_team_accepts_other_user(db_session, test_user):
    other = User(
        email=f"member_{uuid.uuid4()}@example.com",
        hashed_password="x",
        name="Member",
    )
    db_session.add(other)
    await db_session.commit()
    await db_session.refresh(other)

    svc = TeamService(db_session)
    await svc.ensure_personal_team(test_user.id)
    shared = await svc.create_team(name="Shared", owner_user_id=test_user.id)
    row = await svc.add_member(shared.id, other.id, "member")
    assert row.user_id == other.id
    assert row.role == "member"
