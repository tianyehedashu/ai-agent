"""
Chat Service 单元测试
"""

from unittest.mock import AsyncMock, patch
import uuid

import pytest

from core.types import AgentEvent, EventType
from models.user import User
from services.chat import ChatService
from services.session import SessionService


@pytest.mark.unit
class TestChatService:
    """Chat Service 测试"""

    @pytest.fixture
    def service(self, db_session):
        """创建服务实例"""
        return ChatService(db_session)

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

    @pytest.fixture
    def mock_engine(self):
        """Mock AgentEngine"""
        engine = AsyncMock()
        engine.run = AsyncMock()
        engine.resume = AsyncMock()
        return engine

    @pytest.mark.asyncio
    async def test_chat_create_new_session(self, service, db_session):
        """测试: 创建新会话进行对话"""
        # Arrange
        user = await self._create_test_user(db_session)
        user_id = str(user.id)
        message = "Hello"

        # Mock AgentEngine
        mock_event = AgentEvent(
            type=EventType.DONE,
            data={"final_message": {"content": "Hi there"}},
        )

        async def mock_run_generator(*args, **kwargs):
            """模拟异步生成器"""
            yield mock_event

        with patch("services.chat.LangGraphAgentEngine") as mock_engine_class:
            mock_engine = AsyncMock()
            mock_engine.run = mock_run_generator
            mock_engine_class.return_value = mock_engine

            # Act
            events = []
            async for event in service.chat(
                session_id=None,
                message=message,
                agent_id=None,
                user_id=user_id,
            ):
                events.append(event)

            # Assert
            assert len(events) > 0
            # 验证会话已创建
            session_service = SessionService(db_session)
            sessions = await session_service.list_by_user(user_id)
            assert len(sessions) > 0

    @pytest.mark.asyncio
    async def test_chat_use_existing_session(self, service, db_session):
        """测试: 使用现有会话进行对话"""
        # Arrange
        user = await self._create_test_user(db_session)
        user_id = str(user.id)
        session_service = SessionService(db_session)
        session = await session_service.create(user_id=user_id)
        message = "Hello"

        # Mock AgentEngine
        mock_event = AgentEvent(
            type=EventType.DONE,
            data={"final_message": {"content": "Hi there"}},
        )

        async def mock_run_generator(*args, **kwargs):
            """模拟异步生成器"""
            yield mock_event

        with patch("services.chat.LangGraphAgentEngine") as mock_engine_class:
            mock_engine = AsyncMock()
            mock_engine.run = mock_run_generator
            mock_engine_class.return_value = mock_engine

            # Act
            events = []
            async for event in service.chat(
                session_id=str(session.id),
                message=message,
                agent_id=None,
                user_id=user_id,
            ):
                events.append(event)

            # Assert
            assert len(events) > 0

    @pytest.mark.asyncio
    async def test_chat_saves_messages(self, service, db_session):
        """测试: 对话保存消息"""
        # Arrange
        user = await self._create_test_user(db_session)
        user_id = str(user.id)
        message = "Hello"

        # Mock AgentEngine
        mock_event = AgentEvent(
            type=EventType.DONE,
            data={"final_message": {"content": "Hi there"}},
        )

        async def mock_run_generator(*args, **kwargs):
            """模拟异步生成器"""
            yield mock_event

        with patch("services.chat.LangGraphAgentEngine") as mock_engine_class:
            mock_engine = AsyncMock()
            mock_engine.run = mock_run_generator
            mock_engine_class.return_value = mock_engine

            # Act
            async for _event in service.chat(
                session_id=None,
                message=message,
                agent_id=None,
                user_id=user_id,
            ):
                pass

            # Assert
            session_service = SessionService(db_session)
            sessions = await session_service.list_by_user(user_id)
            assert len(sessions) > 0
            messages = await session_service.get_messages(str(sessions[0].id))
            assert len(messages) >= 2  # 用户消息和助手消息

    @pytest.mark.asyncio
    async def test_chat_handles_error(self, service, db_session):
        """测试: 对话处理错误"""
        # Arrange
        user = await self._create_test_user(db_session)
        user_id = str(user.id)
        message = "Hello"

        # Mock AgentEngine 抛出异常
        async def mock_run_generator_error(*args, **kwargs):
            """模拟异步生成器抛出错误"""
            raise Exception("Engine error")
            yield  # 永远不会执行，但保持生成器类型

        with patch("services.chat.LangGraphAgentEngine") as mock_engine_class:
            mock_engine = AsyncMock()
            mock_engine.run = mock_run_generator_error
            mock_engine_class.return_value = mock_engine

            # Act
            events = []
            async for event in service.chat(
                session_id=None,
                message=message,
                agent_id=None,
                user_id=user_id,
            ):
                events.append(event)

            # Assert
            assert len(events) > 0
            assert events[-1].type == "error"

    @pytest.mark.asyncio
    async def test_get_agent_config_with_agent_id(self, service, db_session):
        """测试: 获取指定 Agent 的配置"""
        # Arrange
        from services.agent import AgentService

        user = await self._create_test_user(db_session)
        user_id = str(user.id)
        agent_service = AgentService(db_session)
        agent = await agent_service.create(
            user_id=user_id,
            name="Test Agent",
            system_prompt="Test prompt",
            model="gpt-4",
        )

        # Act
        config = await service._get_agent_config(str(agent.id))

        # Assert
        assert config.name == "Test Agent"
        assert config.model == "gpt-4"
        assert config.system_prompt == "Test prompt"

    @pytest.mark.asyncio
    async def test_get_agent_config_default(self, service):
        """测试: 获取默认配置"""
        # Act
        config = await service._get_agent_config(None)

        # Assert
        assert config.name == "Default Agent"
        assert len(config.tools) > 0
