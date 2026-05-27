"""SQLAlchemyUserRepository 列表筛选与分页。"""

from __future__ import annotations

import uuid

import pytest

from domains.identity.domain.rbac import Role
from domains.identity.domain.repositories.user_repository import UserListFilters
from domains.identity.infrastructure.models.user import User
from domains.identity.infrastructure.repositories.sqlalchemy_user_repository import (
    SQLAlchemyUserRepository,
)


async def _create_user(
    db_session,
    *,
    email: str,
    name: str,
    role: str = Role.USER.value,
    is_active: bool = True,
) -> User:
    user = User(
        email=email,
        hashed_password="hashed",
        name=name,
        role=role,
        is_active=is_active,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.mark.asyncio
async def test_list_page_excludes_anonymous_by_default(db_session) -> None:
    repo = SQLAlchemyUserRepository(db_session)
    suffix = uuid.uuid4().hex[:8]
    await _create_user(
        db_session,
        email=f"real_{suffix}@example.com",
        name="Real User",
    )
    await _create_user(
        db_session,
        email=f"anon_{suffix}@example.com",
        name="Anon User",
        role="anonymous",
    )

    filters = UserListFilters(search=suffix)
    total = await repo.count_filtered(filters)
    items = await repo.list_page(offset=0, limit=20, filters=filters)

    assert total == 1
    assert len(items) == 1
    assert items[0].role == Role.USER.value


@pytest.mark.asyncio
async def test_list_page_filters_by_role_and_is_active(db_session) -> None:
    repo = SQLAlchemyUserRepository(db_session)
    suffix = uuid.uuid4().hex[:8]
    await _create_user(
        db_session,
        email=f"admin_{suffix}@example.com",
        name="Admin User",
        role=Role.ADMIN.value,
    )
    await _create_user(
        db_session,
        email=f"inactive_{suffix}@example.com",
        name="Inactive User",
        is_active=False,
    )

    admin_filters = UserListFilters(search=suffix, role=Role.ADMIN.value)
    assert await repo.count_filtered(admin_filters) == 1

    inactive_filters = UserListFilters(search=suffix, is_active=False)
    assert await repo.count_filtered(inactive_filters) == 1


@pytest.mark.asyncio
async def test_list_page_search_matches_email_or_name(db_session) -> None:
    repo = SQLAlchemyUserRepository(db_session)
    suffix = uuid.uuid4().hex[:8]
    await _create_user(
        db_session,
        email=f"alpha_{suffix}@example.com",
        name="Beta Name",
    )

    by_email = UserListFilters(search=f"alpha_{suffix}")
    by_name = UserListFilters(search="beta name")

    assert await repo.count_filtered(by_email) == 1
    assert await repo.count_filtered(by_name) == 1
