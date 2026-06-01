"""SSO 平台角色持久化集成测试 — 对应 AUTHENTICATION.md 验证清单。"""

from __future__ import annotations

import uuid

from fastapi import status
from httpx import AsyncClient
import pytest
from sqlalchemy import select

from domains.identity.domain.rbac import Role
from domains.identity.infrastructure.models.user import User
from domains.tenancy.infrastructure.membership_adapter import TenancyMembershipAdapter
from domains.tenancy.infrastructure.repositories.team_repository import TeamRepository
from libs.iam.tenancy import TenantId
from tests.helpers.giikin_sso import giikin_sso_headers


@pytest.mark.integration
class TestSsoRolePersistence:
    """SSO JIT 默认 role=user；本地提权 admin 后重登不降级。"""

    @pytest.mark.asyncio
    async def test_jit_default_role_user_with_personal_team_owner(
        self,
        sso_client: AsyncClient,
        db_session,
    ) -> None:
        """验证清单 1：首登 JIT → users.role=user，personal team member=owner。"""
        giikin_id = f"jit-{uuid.uuid4().hex[:8]}"
        headers = giikin_sso_headers(user_id=giikin_id, name="First Login")

        r = await sso_client.get("/api/v1/auth/me", headers=headers)
        assert r.status_code == status.HTTP_200_OK
        body = r.json()
        assert body["role"] == Role.USER.value
        assert body["email"] == f"giikin-{giikin_id}@giikin.sso"

        user_uuid = uuid.UUID(body["id"])
        result = await db_session.execute(select(User).where(User.id == user_uuid))
        user = result.scalar_one()
        assert user.role == Role.USER.value
        assert user.giikin_user_id == giikin_id

        team_repo = TeamRepository(db_session)
        personal = await team_repo.get_personal(user_uuid)
        assert personal is not None

        membership = TenancyMembershipAdapter()
        member_role = await membership.member_role(
            db_session,
            tenant_id=TenantId(personal.id),
            user_id=user_uuid,
        )
        assert member_role == "owner"

    @pytest.mark.asyncio
    async def test_promoted_admin_survives_sso_relogin_and_accesses_admin_api(
        self,
        sso_client: AsyncClient,
        db_session,
    ) -> None:
        """验证清单 2–4：提权 admin 后 SSO 重登 /auth/me 仍为 admin，管理 API 200。"""
        giikin_id = f"adm-{uuid.uuid4().hex[:8]}"
        headers = giikin_sso_headers(user_id=giikin_id, name="Promoted Admin")

        first = await sso_client.get("/api/v1/auth/me", headers=headers)
        assert first.status_code == status.HTTP_200_OK
        user_uuid = uuid.UUID(first.json()["id"])

        result = await db_session.execute(select(User).where(User.id == user_uuid))
        user = result.scalar_one()
        user.role = Role.ADMIN.value
        await db_session.commit()

        second = await sso_client.get("/api/v1/auth/me", headers=headers)
        assert second.status_code == status.HTTP_200_OK
        assert second.json()["role"] == Role.ADMIN.value

        admin_list = await sso_client.get(
            "/api/v1/admin/users",
            headers=headers,
            params={"page": 1, "page_size": 10},
        )
        assert admin_list.status_code == status.HTTP_200_OK

    @pytest.mark.asyncio
    async def test_regular_sso_user_cannot_access_admin_api(
        self,
        sso_client: AsyncClient,
    ) -> None:
        """验证清单 5：普通 SSO user 访问管理 API → 403。"""
        giikin_id = f"usr-{uuid.uuid4().hex[:8]}"
        headers = giikin_sso_headers(user_id=giikin_id)

        me = await sso_client.get("/api/v1/auth/me", headers=headers)
        assert me.status_code == status.HTTP_200_OK
        assert me.json()["role"] == Role.USER.value

        admin_list = await sso_client.get(
            "/api/v1/admin/users",
            headers=headers,
            params={"page": 1, "page_size": 10},
        )
        assert admin_list.status_code == status.HTTP_403_FORBIDDEN
