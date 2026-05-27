"""Admin Users API 集成测试。"""

from __future__ import annotations

import uuid

from fastapi import status
from httpx import AsyncClient
import pytest

from domains.identity.domain.rbac import Role
from domains.identity.infrastructure.models.user import User


@pytest.mark.integration
class TestAdminUsersApi:
    @pytest.mark.asyncio
    async def test_lookup_requires_admin(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        test_user: User,
    ) -> None:
        r = await dev_client.get(
            "/api/v1/admin/users/lookup",
            params={"email": test_user.email},
            headers=auth_headers,
        )
        assert r.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.asyncio
    async def test_lookup_succeeds_for_admin(
        self,
        dev_client: AsyncClient,
        admin_headers: dict[str, str],
        test_user: User,
    ) -> None:
        r = await dev_client.get(
            "/api/v1/admin/users/lookup",
            params={"email": test_user.email},
            headers=admin_headers,
        )
        assert r.status_code == status.HTTP_200_OK
        data = r.json()
        assert data["email"] == test_user.email
        assert data["id"] == str(test_user.id)
        assert data["role"] == Role.USER.value

    @pytest.mark.asyncio
    async def test_lookup_not_found(
        self,
        dev_client: AsyncClient,
        admin_headers: dict[str, str],
    ) -> None:
        r = await dev_client.get(
            "/api/v1/admin/users/lookup",
            params={"email": "nobody@example.com"},
            headers=admin_headers,
        )
        assert r.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_set_role_requires_admin(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        test_user: User,
    ) -> None:
        r = await dev_client.patch(
            f"/api/v1/admin/users/{test_user.id}/role",
            headers=auth_headers,
            json={"role": Role.ADMIN.value},
        )
        assert r.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.asyncio
    async def test_set_role_promote_user(
        self,
        dev_client: AsyncClient,
        admin_headers: dict[str, str],
        test_user: User,
        db_session,
    ) -> None:
        r = await dev_client.patch(
            f"/api/v1/admin/users/{test_user.id}/role",
            headers=admin_headers,
            json={"role": Role.ADMIN.value},
        )
        assert r.status_code == status.HTTP_200_OK
        assert r.json()["role"] == Role.ADMIN.value

        await db_session.refresh(test_user)
        assert test_user.role == Role.ADMIN.value

    @pytest.mark.asyncio
    async def test_set_role_cannot_change_self(
        self,
        dev_client: AsyncClient,
        admin_headers: dict[str, str],
        admin_user: User,
    ) -> None:
        r = await dev_client.patch(
            f"/api/v1/admin/users/{admin_user.id}/role",
            headers=admin_headers,
            json={"role": Role.USER.value},
        )
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_lookup_email_case_insensitive(
        self,
        dev_client: AsyncClient,
        admin_headers: dict[str, str],
        db_session,
    ) -> None:
        mixed_email = f"MixedCase_{uuid.uuid4().hex[:8]}@Example.COM"
        user = User(
            email=mixed_email,
            hashed_password="hashed_password",
            name="Mixed Case",
            role=Role.USER.value,
        )
        db_session.add(user)
        await db_session.commit()

        r = await dev_client.get(
            "/api/v1/admin/users/lookup",
            params={"email": mixed_email.lower()},
            headers=admin_headers,
        )
        assert r.status_code == status.HTTP_200_OK
        assert r.json()["email"] == mixed_email

    @pytest.mark.asyncio
    async def test_demote_admin_when_two_exist(
        self,
        dev_client: AsyncClient,
        admin_headers: dict[str, str],
        test_user: User,
        db_session,
    ) -> None:
        test_user.role = Role.ADMIN.value
        await db_session.commit()

        r = await dev_client.patch(
            f"/api/v1/admin/users/{test_user.id}/role",
            headers=admin_headers,
            json={"role": Role.USER.value},
        )
        assert r.status_code == status.HTTP_200_OK
        assert r.json()["role"] == Role.USER.value

    @pytest.mark.asyncio
    async def test_list_requires_admin(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        r = await dev_client.get("/api/v1/admin/users", headers=auth_headers)
        assert r.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.asyncio
    async def test_list_paginated_for_admin(
        self,
        dev_client: AsyncClient,
        admin_headers: dict[str, str],
        test_user: User,
    ) -> None:
        r = await dev_client.get(
            "/api/v1/admin/users",
            headers=admin_headers,
            params={"page": 1, "page_size": 20},
        )
        assert r.status_code == status.HTTP_200_OK
        data = r.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] >= 1
        emails = [item["email"] for item in data["items"]]
        assert test_user.email in emails
        assert all(item["role"] != "anonymous" for item in data["items"])

    @pytest.mark.asyncio
    async def test_list_search_by_email(
        self,
        dev_client: AsyncClient,
        admin_headers: dict[str, str],
        test_user: User,
    ) -> None:
        r = await dev_client.get(
            "/api/v1/admin/users",
            headers=admin_headers,
            params={"search": test_user.email.split("@")[0]},
        )
        assert r.status_code == status.HTTP_200_OK
        emails = [item["email"] for item in r.json()["items"]]
        assert test_user.email in emails

    @pytest.mark.asyncio
    async def test_list_filter_by_role(
        self,
        dev_client: AsyncClient,
        admin_headers: dict[str, str],
        test_user: User,
    ) -> None:
        r = await dev_client.get(
            "/api/v1/admin/users",
            headers=admin_headers,
            params={"role": Role.USER.value, "search": test_user.email.split("@")[0]},
        )
        assert r.status_code == status.HTTP_200_OK
        assert all(item["role"] == Role.USER.value for item in r.json()["items"])

    @pytest.mark.asyncio
    async def test_get_user_by_id(
        self,
        dev_client: AsyncClient,
        admin_headers: dict[str, str],
        test_user: User,
    ) -> None:
        r = await dev_client.get(
            f"/api/v1/admin/users/{test_user.id}",
            headers=admin_headers,
        )
        assert r.status_code == status.HTTP_200_OK
        data = r.json()
        assert data["id"] == str(test_user.id)
        assert data["email"] == test_user.email
        assert "is_active" in data
        assert "created_at" in data

    @pytest.mark.asyncio
    async def test_update_user_profile(
        self,
        dev_client: AsyncClient,
        admin_headers: dict[str, str],
        test_user: User,
        db_session,
    ) -> None:
        r = await dev_client.patch(
            f"/api/v1/admin/users/{test_user.id}",
            headers=admin_headers,
            json={"name": "Updated Name", "is_active": True},
        )
        assert r.status_code == status.HTTP_200_OK
        assert r.json()["name"] == "Updated Name"

        await db_session.refresh(test_user)
        assert test_user.name == "Updated Name"

    @pytest.mark.asyncio
    async def test_cannot_deactivate_self(
        self,
        dev_client: AsyncClient,
        admin_headers: dict[str, str],
        admin_user: User,
    ) -> None:
        r = await dev_client.patch(
            f"/api/v1/admin/users/{admin_user.id}",
            headers=admin_headers,
            json={"is_active": False},
        )
        assert r.status_code == status.HTTP_400_BAD_REQUEST
