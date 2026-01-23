"""Chat Use Case tests."""

from unittest.mock import AsyncMock, patch
import uuid

import pytest

from shared.types import AgentEvent, EventType
from domains.identity.infrastructure.models.user import User
from domains.runtime.application import ChatUseCase, SessionUseCase


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
            "domains.runtime.application.chat_use_case.LangGraphAgentEngine"
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
            "domains.runtime.application.chat_use_case.LangGraphAgentEngine"
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
            "domains.runtime.application.chat_use_case.LangGraphAgentEngine"
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
            "domains.runtime.application.chat_use_case.LangGraphAgentEngine"
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
        from domains.agent_catalog.application import AgentUseCase

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
