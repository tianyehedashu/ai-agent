"""上游配额凭据写权限单测。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from domains.gateway.application.management import GatewayManagementWriteService
from domains.gateway.domain.errors import CredentialNotFoundError
from domains.tenancy.application.ports import GatewayTeamMembershipSnapshot


def _writes() -> GatewayManagementWriteService:
    return GatewayManagementWriteService(MagicMock())


@pytest.mark.asyncio
async def test_user_byok_returns_owner_personal_team() -> None:
    svc = _writes()
    owner_id = uuid.uuid4()
    personal_team_id = uuid.uuid4()
    cred_id = uuid.uuid4()

    svc._creds.get = AsyncMock(  # type: ignore[method-assign]
        return_value=MagicMock(scope="user", scope_id=owner_id, tenant_id=None)
    )
    svc._ensure_personal_tenant_id = AsyncMock(return_value=personal_team_id)  # type: ignore[method-assign]

    team_id = await svc._assert_upstream_credential_writable(
        cred_id,
        actor_user_id=owner_id,
        is_platform_admin=False,
        request_tenant_id=uuid.uuid4(),
    )

    assert team_id == personal_team_id
    svc._ensure_personal_tenant_id.assert_awaited_once_with(owner_id)


@pytest.mark.asyncio
async def test_user_byok_rejects_non_owner() -> None:
    svc = _writes()
    owner_id = uuid.uuid4()
    other_user = uuid.uuid4()

    svc._creds.get = AsyncMock(  # type: ignore[method-assign]
        return_value=MagicMock(scope="user", scope_id=owner_id, tenant_id=None)
    )

    with pytest.raises(CredentialNotFoundError):
        await svc._assert_upstream_credential_writable(
            uuid.uuid4(),
            actor_user_id=other_user,
            is_platform_admin=False,
            request_tenant_id=uuid.uuid4(),
        )


@pytest.mark.asyncio
async def test_team_credential_requires_admin_membership() -> None:
    svc = _writes()
    actor_id = uuid.uuid4()
    team_id = uuid.uuid4()
    cred_id = uuid.uuid4()

    svc._creds.get = AsyncMock(  # type: ignore[method-assign]
        return_value=MagicMock(scope="team", scope_id=None, tenant_id=team_id)
    )
    svc._teams.list_gateway_team_memberships = AsyncMock(  # type: ignore[method-assign]
        return_value=[
            GatewayTeamMembershipSnapshot(
                team_id=team_id,
                kind="shared",
                role="member",
            )
        ]
    )

    with pytest.raises(CredentialNotFoundError):
        await svc._assert_upstream_credential_writable(
            cred_id,
            actor_user_id=actor_id,
            is_platform_admin=False,
            request_tenant_id=team_id,
        )
