"""Chat SSE 路由的 DB session 生命周期回归测试。"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import Mock
import uuid

import pytest

from domains.agent.domain.types import AgentEvent, EventType
from domains.agent.presentation import chat_router
from domains.identity.presentation.schemas import CurrentUser
from libs.db.permission_context import (
    PermissionContext,
    clear_permission_context,
    set_permission_context,
)


class _FakeChatService:
    async def chat(self, **_kwargs: object) -> AsyncGenerator[AgentEvent, None]:
        yield AgentEvent(type=EventType.TEXT, data={"content": "hello"})

    async def resume(self, **_kwargs: object) -> AsyncGenerator[AgentEvent, None]:
        yield AgentEvent(type=EventType.TEXT, data={"content": "resumed"})


@pytest.mark.asyncio
async def test_chat_stream_creates_service_inside_generator_session(monkeypatch) -> None:
    user_id = uuid.uuid4()
    team_id = uuid.uuid4()
    original_ctx = PermissionContext(
        user_id=user_id,
        role="user",
        team_id=team_id,
        team_role="member",
    )
    set_permission_context(original_ctx)

    events: list[str] = []
    db = object()
    http_request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(checkpointer=None)))
    built = Mock(return_value=_FakeChatService())

    @asynccontextmanager
    async def fake_session_context() -> AsyncGenerator[object, None]:
        events.append("enter-session")
        yield db
        events.append("exit-session")

    def fake_builder(seen_db: object, seen_request: object) -> _FakeChatService:
        events.append("build-service")
        assert seen_db is db
        assert seen_request is http_request
        assert chat_router.get_permission_context() == original_ctx
        return built(seen_db, seen_request)

    monkeypatch.setattr(chat_router, "get_session_context", fake_session_context)
    monkeypatch.setattr(chat_router, "_build_stream_chat_service", fake_builder)

    try:
        response = await chat_router.chat(
            request=chat_router.ChatRequest(message="hello"),
            http_request=http_request,  # type: ignore[arg-type]
            _=None,
            current_user=CurrentUser(
                id=str(user_id),
                email="user@example.com",
                name="User",
                is_anonymous=False,
            ),
        )

        body = [chunk async for chunk in response.body_iterator]
    finally:
        clear_permission_context()

    assert events == ["enter-session", "build-service", "exit-session"]
    assert built.call_count == 1
    assert any("data: [DONE]" in str(chunk) for chunk in body)
