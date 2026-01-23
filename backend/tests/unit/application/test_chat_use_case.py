"""Chat Use Case tests."""

from unittest.mock import AsyncMock, patch
import uuid

import pytest

from domains.agent.application import ChatUseCase, SessionUseCase
from domains.agent.domain.types import (
    AgentEvent,
    EventType,
)
from domains.identity.infrastructure.models.user import User


@pytest.mark.unit
class TestChatUseCase:
    @pytest.fixture
    def service(self, db_session):
        return ChatUseCase(db_session)

    async def _create_test_user(self, db_session) -> User:
        user = User(
            email=f"test_{uuid.uuid4()}@example.com",
            hashed_password="hashed_password",
            name="Test User",
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        return user

    @pytest.mark.asyncio
    async def test_chat_create_new_session(self, service, db_session):
        user = await self._create_test_user(db_session)
        message = "Hello"

        mock_event = AgentEvent(
            type=EventType.DONE,
            data={"final_message": {"content": "Hi there"}},
        )

        async def mock_run_generator(*args, **kwargs):
            yield mock_event

        service.title_service.generate_and_update = AsyncMock()

        with patch(
            "domains.agent.application.chat_use_case.LangGraphAgentEngine"
        ) as mock_engine_class:
            mock_engine = AsyncMock()
            mock_engine.run = mock_run_generator
            mock_engine_class.return_value = mock_engine

            events = []
            async for event in service.chat(
                session_id=None,
                message=message,
                agent_id=None,
                user_id=str(user.id),
            ):
                events.append(event)

            assert len(events) > 0
            sessions = await SessionUseCase(db_session).list_sessions(str(user.id))
            assert len(sessions) > 0

    @pytest.mark.asyncio
    async def test_chat_use_existing_session(self, service, db_session):
        user = await self._create_test_user(db_session)
        session = await SessionUseCase(db_session).create_session(user_id=str(user.id))
        message = "Hello"

        mock_event = AgentEvent(
            type=EventType.DONE,
            data={"final_message": {"content": "Hi there"}},
        )

        async def mock_run_generator(*args, **kwargs):
            yield mock_event

        service.title_service.generate_and_update = AsyncMock()

        with patch(
            "domains.agent.application.chat_use_case.LangGraphAgentEngine"
        ) as mock_engine_class:
            mock_engine = AsyncMock()
            mock_engine.run = mock_run_generator
            mock_engine_class.return_value = mock_engine

            events = []
            async for event in service.chat(
                session_id=str(session.id),
                message=message,
                agent_id=None,
                user_id=str(user.id),
            ):
                events.append(event)

            assert len(events) > 0

    @pytest.mark.asyncio
    async def test_chat_saves_messages(self, service, db_session):
        user = await self._create_test_user(db_session)
        message = "Hello"

        mock_event = AgentEvent(
            type=EventType.DONE,
            data={"final_message": {"content": "Hi there"}},
        )

        async def mock_run_generator(*args, **kwargs):
            yield mock_event

        service.title_service.generate_and_update = AsyncMock()

        with patch(
            "domains.agent.application.chat_use_case.LangGraphAgentEngine"
        ) as mock_engine_class:
            mock_engine = AsyncMock()
            mock_engine.run = mock_run_generator
            mock_engine_class.return_value = mock_engine

            async for _event in service.chat(
                session_id=None,
                message=message,
                agent_id=None,
                user_id=str(user.id),
            ):
                pass

            sessions = await SessionUseCase(db_session).list_sessions(str(user.id))
            assert len(sessions) > 0
            messages = await SessionUseCase(db_session).get_messages(str(sessions[0].id))
            assert len(messages) >= 2

    @pytest.mark.asyncio
    async def test_chat_handles_error(self, service, db_session):
        user = await self._create_test_user(db_session)
        message = "Hello"

        async def mock_run_generator_error(*args, **kwargs):
            raise Exception("Engine error")
            yield

        service.title_service.generate_and_update = AsyncMock()

        with patch(
            "domains.agent.application.chat_use_case.LangGraphAgentEngine"
        ) as mock_engine_class:
            mock_engine = AsyncMock()
            mock_engine.run = mock_run_generator_error
            mock_engine_class.return_value = mock_engine

            events = []
            async for event in service.chat(
                session_id=None,
                message=message,
                agent_id=None,
                user_id=str(user.id),
            ):
                events.append(event)

            assert len(events) > 0
            assert events[-1].type == "error"

    @pytest.mark.asyncio
    async def test_get_agent_config_with_agent_id(self, service, db_session):
        from domains.agent.application import AgentUseCase

        user = await self._create_test_user(db_session)
        agent = await AgentUseCase(db_session).create_agent(
            user_id=str(user.id),
            name="Test Agent",
            system_prompt="Test prompt",
            model="gpt-4",
        )

        config = await service._get_agent_config(str(agent.id))

        assert config.name == "Test Agent"
        assert config.model == "gpt-4"
        assert config.system_prompt == "Test prompt"

    @pytest.mark.asyncio
    async def test_get_agent_config_default(self, service):
        config = await service._get_agent_config(None)

        assert config.name == "Default Agent"
        assert len(config.tools) > 0

    @pytest.mark.asyncio
    async def test_background_task_uses_independent_session(self, service, db_session):
        """测试后台任务使用独立的数据库会话，避免与主请求会话冲突"""
        from contextlib import asynccontextmanager
        from unittest.mock import AsyncMock, patch

        user = await self._create_test_user(db_session)
        session = await SessionUseCase(db_session).create_session(user_id=str(user.id))
        session_id = str(session.id)

        # Mock LLM Gateway 避免实际 API 调用
        mock_llm_response = AsyncMock()
        mock_llm_response.content = "生成的标题"
        service.llm_gateway.chat = AsyncMock(return_value=mock_llm_response)

        # Mock get_session_context 返回测试会话，模拟独立会话
        @asynccontextmanager
        async def mock_session_context():
            yield db_session

        # 提交主请求会话（模拟请求结束）
        await db_session.commit()

        # 验证后台任务可以在独立会话中运行，即使主会话已关闭
        message = "测试消息"
        user_id = str(user.id)

        with patch(
            "domains.agent.application.chat_use_case.get_session_context",
            new=mock_session_context,
        ):
            # 这应该成功，不会抛出 IllegalStateChangeError
            # 后台任务会使用 mock 的独立会话
            await service._generate_title_background(session_id, message, user_id)

        # 验证 LLM 被调用（说明后台任务成功运行）
        assert service.llm_gateway.chat.called
