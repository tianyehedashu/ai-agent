"""UserManager 登录后租户修复（真实 DB）。"""

from __future__ import annotations

from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domains.identity.infrastructure.models.user import User
from domains.identity.infrastructure.user_manager import UserManager
from domains.tenancy.application.team_service import TeamService
from domains.tenancy.infrastructure.repositories.team_repository import TeamRepository


@pytest.mark.asyncio
async def test_on_after_login_recreates_personal_team_when_missing(
    db_session: AsyncSession,
    test_user: User,
) -> None:
    """删除 personal team 后，登录钩子应幂等补齐。"""
    await TeamService(db_session).ensure_personal_team(test_user.id)
    personal = await TeamRepository(db_session).get_personal(test_user.id)
    assert personal is not None
    await TeamRepository(db_session).delete(personal.id)
    await db_session.commit()

    assert await TeamRepository(db_session).get_personal(test_user.id) is None

    user_db = SQLAlchemyUserDatabase(db_session, User)
    manager = UserManager(user_db)

    await manager.on_after_login(test_user, request=None)

    again = await TeamRepository(db_session).get_personal(test_user.id)
    assert again is not None
    assert again.owner_user_id == test_user.id
