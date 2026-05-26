"""TenancyManagementTeamResolveUseCase 单测。"""

import uuid

import pytest

from domains.identity.infrastructure.models.user import User
from domains.tenancy.application.management_team_resolve_use_case import (
    TenancyManagementTeamResolveUseCase,
)
from domains.tenancy.application.team_service import TeamService
from libs.exceptions import TeamPermissionDeniedError


@pytest.mark.asyncio
async def test_resolve_platform_admin_without_membership_gets_synthetic_admin(
    db_session, admin_user: User, test_user: User
) -> None:
    svc = TeamService(db_session)
    await svc.ensure_personal_team(test_user.id)
    outsider_team = await svc.create_team(name="Resolve Outsider", owner_user_id=test_user.id)
    await db_session.commit()

    resolved = await TenancyManagementTeamResolveUseCase(db_session).resolve_management_team(
        user_id=admin_user.id,
        platform_user_role="admin",
        x_team_id=None,
        path_team_id=str(outsider_team.id),
    )
    assert resolved.team_id == outsider_team.id
    assert resolved.team_role == "admin"
    assert resolved.is_platform_admin is True


@pytest.mark.asyncio
async def test_resolve_non_admin_without_membership_denied(
    db_session, test_user: User
) -> None:
    svc = TeamService(db_session)
    await svc.ensure_personal_team(test_user.id)
    other = User(
        email=f"peer_{uuid.uuid4()}@example.com",
        hashed_password="x",
        name="Peer",
    )
    db_session.add(other)
    await db_session.commit()
    await db_session.refresh(other)

    await svc.ensure_personal_team(other.id)
    other_team = await svc.create_team(name="Peer Team", owner_user_id=other.id)
    await db_session.commit()

    with pytest.raises(TeamPermissionDeniedError):
        await TenancyManagementTeamResolveUseCase(db_session).resolve_management_team(
            user_id=test_user.id,
            platform_user_role="user",
            x_team_id=None,
            path_team_id=str(other_team.id),
        )


@pytest.mark.asyncio
async def test_resolve_without_path_uses_personal_team_as_owner(
    db_session, test_user: User
) -> None:
    personal = await TeamService(db_session).ensure_personal_team(test_user.id)
    await db_session.commit()

    resolved = await TenancyManagementTeamResolveUseCase(db_session).resolve_management_team(
        user_id=test_user.id,
        platform_user_role="user",
        x_team_id=None,
        path_team_id=None,
    )
    assert resolved.team_id == personal.id
    assert resolved.team_role == "owner"
