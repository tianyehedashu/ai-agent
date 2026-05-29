"""GiikinIdentityService.resolve_or_provision 单元测试。"""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from domains.identity.application.giikin_identity_service import GiikinIdentityService
from domains.identity.infrastructure.auth.giikin_gateway import GiikinGatewayClaims


@dataclass(frozen=True, slots=True)
class _FakeUser:
    id: uuid.UUID
    email: str
    name: str
    role: str
    giikin_user_id: str | None = None


class _FakeSavepoint:
    """显式 SAVEPOINT 上下文：``__aexit__`` 返回 False，不吞异常（与真实 begin_nested 一致）。"""

    async def __aenter__(self) -> _FakeSavepoint:
        return self

    async def __aexit__(self, *_exc: object) -> bool:
        return False


class _FakeDb:
    def begin_nested(self) -> _FakeSavepoint:
        return _FakeSavepoint()


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

    async def test_concurrent_first_request_falls_back_to_existing(self) -> None:
        """并发首请求：create 撞唯一索引抛 IntegrityError 时，回退到重查既有用户而非 500。"""
        winner = _FakeUser(
            id=uuid.uuid4(),
            email="giikin-3003@giikin.sso",
            name="Winner",
            role="user",
            giikin_user_id="3003",
        )
        user_repo = MagicMock()
        # 首查为空（本协程以为是首请求），重查命中对端已提交的用户
        user_repo.get_by_giikin_user_id = AsyncMock(side_effect=[None, winner])
        user_repo.create = AsyncMock(
            side_effect=IntegrityError("dup", params=None, orig=Exception("unique"))
        )

        service = GiikinIdentityService(
            _FakeDb(),
            user_repo=user_repo,
            tenant_provisioner=MagicMock(),
        )
        claims = GiikinGatewayClaims(user_id="3003", name="Winner", org_code="", shop_id="")

        with patch(
            "domains.identity.application.giikin_identity_service.provision_default_tenant_for_new_user",
            new_callable=AsyncMock,
        ):
            user = await service.resolve_or_provision(claims)

        assert user is winner
        assert user_repo.get_by_giikin_user_id.await_count == 2
