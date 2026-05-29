"""GiikinIdentityService.resolve_or_provision 单元测试。"""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest

from domains.identity.application.giikin_identity_service import GiikinIdentityService
from domains.identity.infrastructure.auth.giikin_gateway import GiikinGatewayClaims


@dataclass(frozen=True, slots=True)
class _FakeUser:
    id: uuid.UUID
    email: str
    name: str
    role: str
    giikin_user_id: str | None = None


@pytest.mark.unit
@pytest.mark.asyncio
class TestGiikinIdentityService:
    async def test_resolve_existing_user_by_giikin_user_id(self) -> None:
        existing = _FakeUser(
            id=uuid.uuid4(),
            email="giikin-1001@giikin.sso",
            name="Existing",
            role="user",
            giikin_user_id="1001",
        )
        user_repo = MagicMock()
        user_repo.get_by_giikin_user_id = AsyncMock(return_value=existing)
        user_repo.create = AsyncMock()

        service = GiikinIdentityService(MagicMock(), user_repo=user_repo)
        claims = GiikinGatewayClaims(
            user_id="1001",
            name="Leo",
            org_code="ORG01",
            shop_id="SHOP9",
        )

        user = await service.resolve_or_provision(claims)

        assert user is existing
        user_repo.get_by_giikin_user_id.assert_awaited_once_with("1001")
        user_repo.create.assert_not_called()

    async def test_provision_new_user_and_default_team(self) -> None:
        created = _FakeUser(
            id=uuid.uuid4(),
            email="giikin-2002@giikin.sso",
            name="New User",
            role="user",
            giikin_user_id="2002",
        )
        user_repo = MagicMock()
        user_repo.get_by_giikin_user_id = AsyncMock(return_value=None)
        user_repo.create = AsyncMock(return_value=created)

        tenant_provisioner = MagicMock()
        db = MagicMock()

        service = GiikinIdentityService(
            db,
            user_repo=user_repo,
            tenant_provisioner=tenant_provisioner,
        )
        claims = GiikinGatewayClaims(
            user_id="2002",
            name="New User",
            org_code="",
            shop_id="",
        )

        with patch(
            "domains.identity.application.giikin_identity_service.provision_default_tenant_for_new_user",
            new_callable=AsyncMock,
        ) as mock_provision:
            user = await service.resolve_or_provision(claims)

        assert user is created
        user_repo.create.assert_awaited_once()
        create_kwargs = user_repo.create.await_args.kwargs
        assert create_kwargs["email"] == "giikin-2002@giikin.sso"
        assert create_kwargs["name"] == "New User"
        assert create_kwargs["role"] == "user"
        assert create_kwargs["giikin_user_id"] == "2002"
        mock_provision.assert_awaited_once_with(
            session=db,
            provisioner=tenant_provisioner,
            user_id=created.id,
            display_name="New User",
            log=mock_provision.await_args.kwargs["log"],
        )
