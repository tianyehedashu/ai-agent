"""
注册流程自动创建 personal team - 单元测试。
"""

from __future__ import annotations

import uuid

import pytest

from domains.gateway.application.team_service import TeamService
from domains.gateway.infrastructure.repositories.team_repository import (
    TeamMemberRepository,
    TeamRepository,
)
from domains.identity.application.user_use_case import UserUseCase


@pytest.mark.unit
class TestPersonalTeamAutoCreation:
    """注册时应当自动创建 personal team"""

    @pytest.mark.asyncio
    async def test_create_user_creates_personal_team(self, db_session):
        use_case = UserUseCase(db_session)
        email = f"test_{uuid.uuid4()}@example.com"

        user = await use_case.create_user(
            email=email,
            password="SecurePass123!",
            name="Personal Team User",
        )

        # 验证 personal team 存在
        team_repo = TeamRepository(db_session)
        team = await team_repo.get_personal(user.id)
        assert team is not None
        assert team.kind == "personal"
        assert team.owner_user_id == user.id

        # 团队成员里 owner 角色存在
        member_repo = TeamMemberRepository(db_session)
        member = await member_repo.get(team.id, user.id)
        assert member is not None
        assert member.role == "owner"

    @pytest.mark.asyncio
    async def test_ensure_personal_team_idempotent(self, db_session, test_user):
        service = TeamService(db_session)
        team_a = await service.ensure_personal_team(test_user.id)
        team_b = await service.ensure_personal_team(test_user.id)
        assert team_a.id == team_b.id

    @pytest.mark.asyncio
    async def test_create_shared_team(self, db_session, test_user):
        service = TeamService(db_session)
        team = await service.create_team(name="Team A", owner_user_id=test_user.id)
        assert team.kind == "shared"

        # owner 自动加入
        member_repo = TeamMemberRepository(db_session)
        member = await member_repo.get(team.id, test_user.id)
        assert member is not None
        assert member.role == "owner"

    @pytest.mark.asyncio
    async def test_cannot_remove_personal_owner(self, db_session, test_user):
        service = TeamService(db_session)
        team = await service.ensure_personal_team(test_user.id)
        with pytest.raises(ValueError):
            await service.remove_member(team.id, test_user.id)
