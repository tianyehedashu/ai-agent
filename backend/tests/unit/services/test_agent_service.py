"""
Agent Service 单元测试
"""

import uuid

import pytest

from exceptions import NotFoundError
from models.user import User
from services.agent import AgentService


@pytest.mark.unit
class TestAgentService:
    """Agent Service 测试"""

    async def _create_test_user(self, db_session) -> User:
        """创建测试用户辅助函数"""
        user = User(
            email=f"test_{uuid.uuid4()}@example.com",
            password_hash="hashed_password",
            name="Test User",
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        return user

    @pytest.mark.asyncio
    async def test_create_agent(self, db_session):
        """测试: 创建 Agent"""
        # Arrange
        user = await self._create_test_user(db_session)
        service = AgentService(db_session)
        user_id = str(user.id)

        # Act
        agent = await service.create(
            user_id=user_id,
            name="Test Agent",
            system_prompt="You are a helpful assistant",
            description="Test description",
        )

        # Assert
        assert agent.id is not None
        assert agent.name == "Test Agent"
        assert agent.system_prompt == "You are a helpful assistant"
        assert agent.description == "Test description"
        assert agent.user_id == uuid.UUID(user_id)

    @pytest.mark.asyncio
    async def test_get_by_id(self, db_session):
        """测试: 通过 ID 获取 Agent"""
        # Arrange
        user = await self._create_test_user(db_session)
        service = AgentService(db_session)
        user_id = str(user.id)
        agent = await service.create(
            user_id=user_id,
            name="Test Agent",
            system_prompt="Test prompt",
        )

        # Act
        found = await service.get_by_id(str(agent.id))

        # Assert
        assert found is not None
        assert found.id == agent.id
        assert found.name == "Test Agent"

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, db_session):
        """测试: 获取不存在的 Agent"""
        # Arrange
        service = AgentService(db_session)

        # Act
        found = await service.get_by_id(str(uuid.uuid4()))

        # Assert
        assert found is None

    @pytest.mark.asyncio
    async def test_get_by_id_or_raise(self, db_session):
        """测试: 通过 ID 获取 Agent，不存在则抛出异常"""
        # Arrange
        user = await self._create_test_user(db_session)
        service = AgentService(db_session)
        user_id = str(user.id)
        agent = await service.create(
            user_id=user_id,
            name="Test Agent",
            system_prompt="Test prompt",
        )

        # Act
        found = await service.get_by_id_or_raise(str(agent.id))

        # Assert
        assert found.id == agent.id

    @pytest.mark.asyncio
    async def test_get_by_id_or_raise_not_found(self, db_session):
        """测试: 获取不存在的 Agent 抛出异常"""
        # Arrange
        service = AgentService(db_session)

        # Act & Assert
        with pytest.raises(NotFoundError):
            await service.get_by_id_or_raise(str(uuid.uuid4()))

    @pytest.mark.asyncio
    async def test_list_by_user(self, db_session):
        """测试: 获取用户的 Agent 列表"""
        # Arrange
        user = await self._create_test_user(db_session)
        service = AgentService(db_session)
        user_id = str(user.id)

        # 创建多个 Agent
        agent1 = await service.create(
            user_id=user_id,
            name="Agent 1",
            system_prompt="Prompt 1",
        )
        agent2 = await service.create(
            user_id=user_id,
            name="Agent 2",
            system_prompt="Prompt 2",
        )

        # Act
        agents = await service.list_by_user(user_id)

        # Assert
        assert len(agents) >= 2
        agent_ids = [a.id for a in agents]
        assert agent1.id in agent_ids
        assert agent2.id in agent_ids

    @pytest.mark.asyncio
    async def test_list_by_user_with_pagination(self, db_session):
        """测试: 分页获取用户的 Agent 列表"""
        # Arrange
        user = await self._create_test_user(db_session)
        service = AgentService(db_session)
        user_id = str(user.id)

        # 创建多个 Agent
        for i in range(5):
            await service.create(
                user_id=user_id,
                name=f"Agent {i}",
                system_prompt=f"Prompt {i}",
            )

        # Act
        agents = await service.list_by_user(user_id, skip=0, limit=2)

        # Assert
        assert len(agents) == 2

    @pytest.mark.asyncio
    async def test_update_agent(self, db_session):
        """测试: 更新 Agent"""
        # Arrange
        user = await self._create_test_user(db_session)
        service = AgentService(db_session)
        user_id = str(user.id)
        agent = await service.create(
            user_id=user_id,
            name="Original Name",
            system_prompt="Original prompt",
            temperature=0.7,
        )

        # Act
        updated = await service.update(
            str(agent.id),
            name="Updated Name",
            temperature=0.9,
        )

        # Assert
        assert updated.name == "Updated Name"
        assert updated.temperature == 0.9
        assert updated.system_prompt == "Original prompt"  # 未更新的字段保持不变

    @pytest.mark.asyncio
    async def test_update_agent_not_found(self, db_session):
        """测试: 更新不存在的 Agent 抛出异常"""
        # Arrange
        service = AgentService(db_session)

        # Act & Assert
        with pytest.raises(NotFoundError):
            await service.update(
                str(uuid.uuid4()),
                name="New Name",
            )

    @pytest.mark.asyncio
    async def test_delete_agent(self, db_session):
        """测试: 删除 Agent"""
        # Arrange
        user = await self._create_test_user(db_session)
        service = AgentService(db_session)
        user_id = str(user.id)
        agent = await service.create(
            user_id=user_id,
            name="Test Agent",
            system_prompt="Test prompt",
        )

        # Act
        await service.delete(str(agent.id))

        # Assert
        found = await service.get_by_id(str(agent.id))
        assert found is None

    @pytest.mark.asyncio
    async def test_delete_agent_not_found(self, db_session):
        """测试: 删除不存在的 Agent 抛出异常"""
        # Arrange
        service = AgentService(db_session)

        # Act & Assert
        with pytest.raises(NotFoundError):
            await service.delete(str(uuid.uuid4()))
