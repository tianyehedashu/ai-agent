"""PersonalTeamProvisioner 幂等封装。"""

from __future__ import annotations

import pytest

from domains.tenancy.application.personal_team_provisioner import PersonalTeamProvisioner
from domains.tenancy.application.team_service import TeamService


@pytest.mark.asyncio
async def test_personal_team_provisioner_idempotent(db_session, test_user) -> None:
    prov = PersonalTeamProvisioner(db_session)
    tid_a = await prov.ensure_personal_team(test_user.id)
    tid_b = await prov.ensure_personal_team(test_user.id)
    assert tid_a == tid_b
    team = await TeamService(db_session).get_team(tid_a)
    assert team is not None
    assert team.kind == "personal"
