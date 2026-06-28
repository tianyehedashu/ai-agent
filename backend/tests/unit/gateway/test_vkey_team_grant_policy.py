"""vkey_team_grant_policy 单测。"""

from __future__ import annotations

import uuid

import pytest

from domains.gateway.application.vkey.management.vkey_team_grant_policy import (
    assert_actor_member_of_vkey_grant_targets,
    resolve_extra_vkey_grant_tenant_ids,
)
from domains.gateway.domain.errors import VkeyGrantTargetNotMemberError
from domains.tenancy.application.team_service import TeamService


@pytest.mark.asyncio
async def test_resolve_extra_skips_bound_and_dedupes(db_session, test_user) -> None:
    teams = TeamService(db_session)
    primary = await teams.ensure_personal_team(test_user.id)
    shared = await teams.create_team(
        name=f"shared-{uuid.uuid4().hex[:6]}",
        owner_user_id=test_user.id,
    )
    extra = await resolve_extra_vkey_grant_tenant_ids(
        db_session,
        actor_user_id=test_user.id,
        bound_team_id=primary.id,
        requested_tenant_ids=[primary.id, shared.id, shared.id],
    )
    assert extra == [shared.id]


@pytest.mark.asyncio
async def test_resolve_extra_rejects_non_member(db_session, test_user) -> None:
    primary = await TeamService(db_session).ensure_personal_team(test_user.id)
    foreign = uuid.uuid4()
    with pytest.raises(VkeyGrantTargetNotMemberError) as exc:
        await resolve_extra_vkey_grant_tenant_ids(
            db_session,
            actor_user_id=test_user.id,
            bound_team_id=primary.id,
            requested_tenant_ids=[foreign],
        )
    assert foreign in exc.value.tenant_ids


@pytest.mark.asyncio
async def test_assert_grant_targets_rejects_non_member(db_session, test_user) -> None:
    primary = await TeamService(db_session).ensure_personal_team(test_user.id)
    foreign = uuid.uuid4()
    with pytest.raises(VkeyGrantTargetNotMemberError):
        await assert_actor_member_of_vkey_grant_targets(
            db_session,
            actor_user_id=test_user.id,
            tenant_ids=[primary.id, foreign],
        )


@pytest.mark.asyncio
async def test_assert_grant_targets_allows_membership_teams(db_session, test_user) -> None:
    teams = TeamService(db_session)
    primary = await teams.ensure_personal_team(test_user.id)
    shared = await teams.create_team(
        name=f"shared-{uuid.uuid4().hex[:6]}",
        owner_user_id=test_user.id,
    )
    await assert_actor_member_of_vkey_grant_targets(
        db_session,
        actor_user_id=test_user.id,
        tenant_ids=[primary.id, shared.id],
    )
