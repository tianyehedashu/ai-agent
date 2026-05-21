"""Chat Use Case tests."""

from unittest.mock import AsyncMock, patch
import uuid

import pytest

from domains.agent.application import ChatUseCase
from domains.agent.domain.types import (
    AgentEvent,
    EventType,
)
from domains.identity.infrastructure.models.user import User
from libs.api.deps import build_session_use_case
from libs.iam.permission_context import clear_permission_context, set_permission_context


@pytest.mark.unit
class TestChatUseCase:
    @pytest.fixture
    def service(self, db_session):
        from unittest.mock import AsyncMock

        from domains.agent.application.chat_model_resolution_use_case import (
            ChatModelResolutionUseCase,
        )

        session_use_case = build_session_use_case(db_session)
        catalog = AsyncMock()
        catalog.list_visible_models = AsyncMock(
            return_value=[{"id": "deepseek/deepseek-chat", "display_name": "DeepSeek"}]
        )
        from domains.agent.infrastructure.memory.vector_store_factory import (
            build_memory_indexing_service,
        )

        model_resolution = ChatModelResolutionUseCase(db_session, catalog=catalog)

        class _FakeEmbedding:
            async def embed(self, text: str) -> list[float]:
                return [0.0] * 4

        memory_indexing = build_memory_indexing_service(embedding=_FakeEmbedding())
        return ChatUseCase(
            db_session,
            session_use_case=session_use_case,
            session_use_case_factory=build_session_use_case,
            memory_indexing=memory_indexing,
            model_catalog=catalog,
            model_resolution_use_case=model_resolution,
        )

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
        from tests.helpers.permission_context import permission_context_for_user

        ctx = await permission_context_for_user(db_session, user_id=user.id)
        set_permission_context(ctx)
        try:
            message = "Hello"

            mock_event = AgentEvent(
                type=EventType.DONE,
                data={"final_message": {"content": "Hi there"}},
            )

            async def mock_run_generator(*args, **kwargs):
                yield mock_event

            service.title_service.generate_and_update = AsyncMock()

            with patch(
                "domains.agent.application.chat_engine.LangGraphAgentEngine"
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
                sessions = await build_session_use_case(db_session).list_sessions(str(user.id))
                assert len(sessions) > 0
        finally:
            clear_permission_context()

    @pytest.mark.asyncio
    async def test_chat_use_existing_session(self, service, db_session):
        user = await self._create_test_user(db_session)
        from tests.helpers.permission_context import permission_context_for_user

        ctx = await permission_context_for_user(db_session, user_id=user.id)
        set_permission_context(ctx)
        try:
            session = await build_session_use_case(db_session).create_session(
                user_id=str(user.id)
            )
            message = "Hello"

            mock_event = AgentEvent(
                type=EventType.DONE,
                data={"final_message": {"content": "Hi there"}},
            )

            async def mock_run_generator(*args, **kwargs):
                yield mock_event

            service.title_service.generate_and_update = AsyncMock()

            with patch(
                "domains.agent.application.chat_engine.LangGraphAgentEngine"
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
        finally:
            clear_permission_context()

    @pytest.mark.asyncio
    async def test_chat_saves_messages(self, service, db_session):
        user = await self._create_test_user(db_session)
        from tests.helpers.permission_context import permission_context_for_user

        ctx = await permission_context_for_user(db_session, user_id=user.id)
        set_permission_context(ctx)
        try:
            message = "Hello"

            mock_event = AgentEvent(
                type=EventType.DONE,
                data={"final_message": {"content": "Hi there"}},
            )

            async def mock_run_generator(*args, **kwargs):
                yield mock_event

            service.title_service.generate_and_update = AsyncMock()

            with patch(
                "domains.agent.application.chat_engine.LangGraphAgentEngine"
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

                sessions = await build_session_use_case(db_session).list_sessions(str(user.id))
                assert len(sessions) > 0
                messages = await build_session_use_case(db_session).get_messages(
                    str(sessions[0].id)
                )
                assert len(messages) >= 2
        finally:
            clear_permission_context()

    @pytest.mark.asyncio
    async def test_chat_handles_error(self, service, db_session):
        user = await self._create_test_user(db_session)
        from tests.helpers.permission_context import permission_context_for_user

        ctx = await permission_context_for_user(db_session, user_id=user.id)
        set_permission_context(ctx)
        try:
            message = "Hello"

            async def mock_run_generator_error(*args, **kwargs):
                raise Exception("Engine error")
                yield

            service.title_service.generate_and_update = AsyncMock()

            with patch(
                "domains.agent.application.chat_engine.LangGraphAgentEngine"
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
        finally:
            clear_permission_context()

    @pytest.mark.asyncio
    async def test_get_agent_config_with_agent_id(self, service, db_session):
        from domains.agent.application import AgentUseCase

        user = await self._create_test_user(db_session)
        from tests.helpers.permission_context import permission_context_for_user

        ctx = await permission_context_for_user(db_session, user_id=user.id)
        set_permission_context(ctx)
        try:
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
        finally:
            clear_permission_context()

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
        from tests.helpers.permission_context import permission_context_for_user

        ctx = await permission_context_for_user(db_session, user_id=user.id)
        set_permission_context(ctx)
        try:
            session = await build_session_use_case(db_session).create_session(
                user_id=str(user.id)
            )
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

            with (
                patch(
                    "domains.agent.application.chat_use_case.get_session_context",
                    new=mock_session_context,
                ),
                patch(
                    "domains.session.application.title_use_case.require_scenario_default",
                    new=AsyncMock(return_value="test/fast-model"),
                ),
            ):
                # 这应该成功，不会抛出 IllegalStateChangeError
                # 后台任务会使用 mock 的独立会话
                await service._generate_title_background(session_id, message, user_id)

            # 验证 LLM 被调用（说明后台任务成功运行）
            assert service.llm_gateway.chat.called
        finally:
            clear_permission_context()

    @pytest.mark.asyncio
    async def test_chat_auto_generates_title_on_first_message(self, service, db_session):
        """测试：发送第一条消息后，会话标题应该自动生成"""
        from contextlib import asynccontextmanager
        from unittest.mock import AsyncMock, patch

        user = await self._create_test_user(db_session)
        from tests.helpers.permission_context import permission_context_for_user

        ctx = await permission_context_for_user(db_session, user_id=user.id)
        set_permission_context(ctx)
        try:
            message = "我想学习 Python 编程，请给我一些建议"

            mock_event = AgentEvent(
                type=EventType.DONE,
                data={"final_message": {"content": "好的，我来帮你学习 Python"}},
            )

            async def mock_run_generator(*args, **kwargs):
                yield mock_event

            # Mock LLM Gateway 返回生成的标题
            mock_llm_response = AsyncMock()
            mock_llm_response.content = "Python 编程学习"
            service.llm_gateway.chat = AsyncMock(return_value=mock_llm_response)
            # Mock get_session_context 返回测试会话，用于后台任务
            @asynccontextmanager
            async def mock_session_context():
                yield db_session

            with (
                patch(
                    "domains.agent.application.chat_engine.LangGraphAgentEngine"
                ) as mock_engine_class,
                patch(
                    "domains.agent.application.chat_use_case.get_session_context",
                    new=mock_session_context,
                ),
                patch(
                    "domains.session.application.title_use_case.require_scenario_default",
                    new=AsyncMock(return_value="test/fast-model"),
                ),
            ):
                mock_engine = AsyncMock()
                mock_engine.run = mock_run_generator
                mock_engine_class.return_value = mock_engine

                # 发送第一条消息
                events = []
                async for event in service.chat(
                    session_id=None,
                    message=message,
                    agent_id=None,
                    user_id=str(user.id),
                ):
                    events.append(event)

                # 验证会话已创建
                sessions = await build_session_use_case(db_session).list_sessions(str(user.id))
                assert len(sessions) > 0
                session = sessions[0]

                # 等待后台任务完成（任务可能在 chat 流式过程中已结束并从集合移除）
                import asyncio

                pending = list(service._background_tasks)
                if pending:
                    await asyncio.gather(*pending, return_exceptions=True)

                assert service.llm_gateway.chat.called

                # 刷新会话以获取最新数据
                await db_session.refresh(session)

                # 验证标题已被生成并更新
                # 由于使用了 mock，标题应该被更新为 "Python 编程学习"
                assert session.title is not None
                assert session.title != ""
                # 验证标题是生成的内容（不是默认标题）
                assert (
                    "Python" in session.title or "编程" in session.title or "学习" in session.title
                )
        finally:
            clear_permission_context()
