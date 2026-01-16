"""
Session Service 单元测试
"""

import uuid

import pytest

from core.types import MessageRole
from exceptions import NotFoundError
from models.user import User
from services.session import SessionService


@pytest.mark.unit
class TestSessionService:
    """Session Service 测试"""

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
    async def test_create_session(self, db_session):
        """测试: 创建会话"""
        # Arrange
        user = await self._create_test_user(db_session)
        service = SessionService(db_session)
        user_id = str(user.id)

        # Act
        session = await service.create(user_id=user_id, title="Test Session")

        # Assert
        assert session.id is not None
        assert session.title == "Test Session"
        assert session.user_id == uuid.UUID(user_id)

    @pytest.mark.asyncio
    async def test_create_session_with_agent(self, db_session):
        """测试: 创建带 Agent 的会话"""
        # Arrange
        user = await self._create_test_user(db_session)
        service = SessionService(db_session)
        user_id = str(user.id)
        # 创建 agent（需要先有 user）
        from services.agent import AgentService

        agent_service = AgentService(db_session)
        agent = await agent_service.create(
            user_id=user_id,
            name="Test Agent",
            system_prompt="Test prompt",
        )
        agent_id = str(agent.id)

        # Act
        session = await service.create(
            user_id=user_id,
            agent_id=agent_id,
        )

        # Assert
        assert session.agent_id == uuid.UUID(agent_id)

    @pytest.mark.asyncio
    async def test_get_by_id(self, db_session):
        """测试: 通过 ID 获取会话"""
        # Arrange
        service = SessionService(db_session)
        user = await self._create_test_user(db_session)
        user_id = str(user.id)
        session = await service.create(user_id=user_id)

        # Act
        found = await service.get_by_id(str(session.id))

        # Assert
        assert found is not None
        assert found.id == session.id

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, db_session):
        """测试: 获取不存在的会话"""
        # Arrange
        service = SessionService(db_session)

        # Act
        found = await service.get_by_id(str(uuid.uuid4()))

        # Assert
        assert found is None

    @pytest.mark.asyncio
    async def test_get_by_id_or_raise(self, db_session):
        """测试: 通过 ID 获取会话，不存在则抛出异常"""
        # Arrange
        service = SessionService(db_session)
        user = await self._create_test_user(db_session)
        user_id = str(user.id)
        session = await service.create(user_id=user_id)

        # Act
        found = await service.get_by_id_or_raise(str(session.id))

        # Assert
        assert found.id == session.id

    @pytest.mark.asyncio
    async def test_get_by_id_or_raise_not_found(self, db_session):
        """测试: 获取不存在的会话抛出异常"""
        # Arrange
        service = SessionService(db_session)

        # Act & Assert
        with pytest.raises(NotFoundError):
            await service.get_by_id_or_raise(str(uuid.uuid4()))

    @pytest.mark.asyncio
    async def test_list_by_user(self, db_session):
        """测试: 获取用户的会话列表"""
        # Arrange
        service = SessionService(db_session)
        user = await self._create_test_user(db_session)
        user_id = str(user.id)

        # 创建多个会话
        session1 = await service.create(user_id=user_id, title="Session 1")
        session2 = await service.create(user_id=user_id, title="Session 2")

        # Act
        sessions = await service.list_by_user(user_id)

        # Assert
        assert len(sessions) >= 2
        session_ids = [s.id for s in sessions]
        assert session1.id in session_ids
        assert session2.id in session_ids

    @pytest.mark.asyncio
    async def test_list_by_user_with_agent_filter(self, db_session):
        """测试: 按 Agent 筛选会话"""
        # Arrange
        user = await self._create_test_user(db_session)
        service = SessionService(db_session)
        user_id = str(user.id)
        # 创建 agent
        from services.agent import AgentService

        agent_service = AgentService(db_session)
        agent = await agent_service.create(
            user_id=user_id,
            name="Test Agent",
            system_prompt="Test prompt",
        )
        agent_id = str(agent.id)

        # 创建带 Agent 的会话
        await service.create(
            user_id=user_id,
            agent_id=agent_id,
        )
        # 创建不带 Agent 的会话
        await service.create(user_id=user_id)

        # Act
        sessions = await service.list_by_user(user_id, agent_id=agent_id)

        # Assert
        assert len(sessions) >= 1
        assert all(s.agent_id == uuid.UUID(agent_id) for s in sessions)

    @pytest.mark.asyncio
    async def test_update_session(self, db_session):
        """测试: 更新会话"""
        # Arrange
        service = SessionService(db_session)
        user = await self._create_test_user(db_session)
        user_id = str(user.id)
        session = await service.create(user_id=user_id, title="Original Title")

        # Act
        updated = await service.update(
            str(session.id),
            title="Updated Title",
            status="active",
        )

        # Assert
        assert updated.title == "Updated Title"
        assert updated.status == "active"

    @pytest.mark.asyncio
    async def test_update_session_not_found(self, db_session):
        """测试: 更新不存在的会话抛出异常"""
        # Arrange
        service = SessionService(db_session)

        # Act & Assert
        with pytest.raises(NotFoundError):
            await service.update(str(uuid.uuid4()), title="New Title")

    @pytest.mark.asyncio
    async def test_delete_session(self, db_session):
        """测试: 删除会话"""
        # Arrange
        service = SessionService(db_session)
        user = await self._create_test_user(db_session)
        user_id = str(user.id)
        session = await service.create(user_id=user_id)

        # Act
        await service.delete(str(session.id))

        # Assert
        found = await service.get_by_id(str(session.id))
        assert found is None

    @pytest.mark.asyncio
    async def test_get_messages(self, db_session):
        """测试: 获取会话消息"""
        # Arrange
        service = SessionService(db_session)
        user = await self._create_test_user(db_session)
        user_id = str(user.id)
        session = await service.create(user_id=user_id)

        # 添加消息
        await service.add_message(
            session_id=str(session.id),
            role=MessageRole.USER,
            content="Hello",
        )
        await service.add_message(
            session_id=str(session.id),
            role=MessageRole.ASSISTANT,
            content="Hi there",
        )

        # Act
        messages = await service.get_messages(str(session.id))

        # Assert
        assert len(messages) == 2
        assert messages[0].content == "Hello"
        assert messages[1].content == "Hi there"

    @pytest.mark.asyncio
    async def test_add_message(self, db_session):
        """测试: 添加消息"""
        # Arrange
        service = SessionService(db_session)
        user = await self._create_test_user(db_session)
        user_id = str(user.id)
        session = await service.create(user_id=user_id)

        # Act
        message = await service.add_message(
            session_id=str(session.id),
            role=MessageRole.USER,
            content="Test message",
            token_count=10,
        )

        # Assert
        assert message.id is not None
        assert message.content == "Test message"
        assert message.role == MessageRole.USER.value
        assert message.token_count == 10

        # 验证会话统计更新
        await db_session.refresh(session)
        assert session.message_count == 1
        assert session.token_count == 10

    @pytest.mark.asyncio
    async def test_add_message_with_tool_calls(self, db_session):
        """测试: 添加带工具调用的消息"""
        # Arrange
        service = SessionService(db_session)
        user = await self._create_test_user(db_session)
        user_id = str(user.id)
        session = await service.create(user_id=user_id)

        tool_calls = {
            "id": "call_123",
            "name": "read_file",
            "arguments": {"path": "/tmp/test.txt"},
        }

        # Act
        message = await service.add_message(
            session_id=str(session.id),
            role=MessageRole.ASSISTANT,
            tool_calls=tool_calls,
        )

        # Assert
        assert message.tool_calls == tool_calls
