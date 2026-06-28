"""Playground 凭据聚合读侧单测。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from unittest.mock import AsyncMock
import uuid

import pytest

from domains.gateway.application.credential.management.credential_read_model import (
    CredentialReadModel,
)
from domains.gateway.application.credential.management.playground_credential_reads import (
    list_playground_credential_summaries_for_actor,
)
from domains.tenancy.application.ports import GatewayTeamMembershipSnapshot


def _cred(
    *,
    cred_id: uuid.UUID,
    scope: str | None,
    tenant_id: uuid.UUID | None = None,
    name: str = "cred",
    is_active: bool = True,
) -> CredentialReadModel:
    return CredentialReadModel(
        id=cred_id,
        tenant_id=tenant_id,
        scope=scope,
        scope_id=None,
        provider="openai",
        name=name,
        api_base=None,
        extra=None,
        is_active=is_active,
        created_at=datetime.now(tz=UTC),
        api_key_encrypted="enc",
    )


@dataclass
class _FakeListing:
    memberships: list[GatewayTeamMembershipSnapshot]

    async def list_gateway_team_memberships(
        self,
        _user_id: uuid.UUID,
        *,
        is_platform_admin: bool,
        search: str | None = None,
        exclude_anonymous_personal: bool = True,
    ) -> list[GatewayTeamMembershipSnapshot]:
        _ = (is_platform_admin, search, exclude_anonymous_personal)
        return self.memberships


@pytest.mark.asyncio
async def test_list_playground_credential_summaries_uses_membership_only_teams() -> None:
    user_id = uuid.uuid4()
    listing = AsyncMock()
    listing.list_gateway_team_memberships = AsyncMock(return_value=[])

    reads = AsyncMock()
    reads.list_user_credentials = AsyncMock(return_value=[])

    await list_playground_credential_summaries_for_actor(
        AsyncMock(),
        reads,
        user_id=user_id,
        is_platform_admin=True,
        team_listing=listing,
    )

    listing.list_gateway_team_memberships.assert_awaited_once_with(
        user_id,
        is_platform_admin=False,
    )


@pytest.mark.asyncio
async def test_list_playground_credential_summaries_merges_user_team_and_system() -> None:
    user_id = uuid.uuid4()
    personal_team = uuid.uuid4()
    shared_team = uuid.uuid4()
    user_cred_id = uuid.uuid4()
    team_cred_id = uuid.uuid4()
    system_cred_id = uuid.uuid4()

    listing = _FakeListing(
        memberships=[
            GatewayTeamMembershipSnapshot(team_id=personal_team, kind="personal", role="owner"),
            GatewayTeamMembershipSnapshot(team_id=shared_team, kind="shared", role="member"),
        ]
    )

    reads = AsyncMock()
    reads.list_user_credentials = AsyncMock(
        return_value=[_cred(cred_id=user_cred_id, scope="user", name="my")]
    )
    reads.list_credential_summaries_for_team = AsyncMock(
        side_effect=lambda team_id, **_: (
            [
                _cred(cred_id=team_cred_id, scope="team", tenant_id=shared_team, name="team"),
                _cred(cred_id=system_cred_id, scope="system", name="sys"),
            ]
            if team_id == shared_team
            else [_cred(cred_id=system_cred_id, scope="system", name="sys")]
        )
    )

    rows = await list_playground_credential_summaries_for_actor(
        AsyncMock(),
        reads,
        user_id=user_id,
        is_platform_admin=False,
        team_listing=listing,
    )

    by_id = {item.credential.id: item for item in rows}
    assert set(by_id) == {user_cred_id, team_cred_id, system_cred_id}
    assert by_id[user_cred_id].context_team_id == personal_team
    assert by_id[team_cred_id].context_team_id == shared_team
    assert by_id[system_cred_id].context_team_id == personal_team


@pytest.mark.asyncio
async def test_list_playground_credential_summaries_skips_inactive() -> None:
    user_id = uuid.uuid4()
    personal_team = uuid.uuid4()
    active_id = uuid.uuid4()
    inactive_id = uuid.uuid4()

    listing = _FakeListing(
        memberships=[
            GatewayTeamMembershipSnapshot(team_id=personal_team, kind="personal", role="owner"),
        ]
    )
    reads = AsyncMock()
    reads.list_user_credentials = AsyncMock(
        return_value=[
            _cred(cred_id=active_id, scope="user", name="active"),
            _cred(cred_id=inactive_id, scope="user", name="off", is_active=False),
        ]
    )
    reads.list_credential_summaries_for_team = AsyncMock(return_value=[])

    rows = await list_playground_credential_summaries_for_actor(
        AsyncMock(),
        reads,
        user_id=user_id,
        is_platform_admin=False,
        team_listing=listing,
    )

    assert {item.credential.id for item in rows} == {active_id}
