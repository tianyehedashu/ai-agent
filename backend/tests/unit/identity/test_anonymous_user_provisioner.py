"""AnonymousUserProvisioner 幂等。"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from domains.identity.application.anonymous_user_provisioner import AnonymousUserProvisioner
from domains.identity.domain.types import Principal
from domains.identity.infrastructure.models.user import User
from domains.tenancy.infrastructure.models.team import Team


@pytest.mark.asyncio
async def test_ensure_shadow_user_idempotent(db_session) -> None:
    cookie = uuid.uuid4().hex
    prov = AnonymousUserProvisioner(db_session)
    uid1 = await prov.ensure_shadow_user(cookie)
    uid2 = await prov.ensure_shadow_user(cookie)
    assert uid1 == uid2

    user = await db_session.get(User, uid1)
    assert user is not None
    assert user.role == "anonymous"
    assert user.email == Principal.make_anonymous_email(cookie)

    teams = (
        await db_session.execute(
            select(Team).where(Team.owner_user_id == uid1, Team.kind == "personal")
        )
    ).scalars().all()
    assert len(teams) >= 1
