"""AgentLlmFacade 单元测试。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from domains.agent.infrastructure.llm.agent_llm_facade import AgentLlmFacade, AgentLlmResponse
from domains.gateway.application.ports import GatewayResponse, GatewayStreamChunk
from tests.helpers.bridge_identity import patch_bridge_identity


@pytest.fixture
def facade() -> AgentLlmFacade:
    from bootstrap.config import settings

    return AgentLlmFacade(config=settings, gateway_proxy=MagicMock())


@pytest.mark.asyncio
async def test_chat_invokes_gateway_proxy(facade: AgentLlmFacade) -> None:
    mock_proxy = facade._gateway_proxy
    mock_proxy.chat_completion = AsyncMock(
        return_value=GatewayResponse(content="ok", model="gpt-4")
    )
    with patch_bridge_identity():
        result = await facade.chat(
            messages=[{"role": "user", "content": "hi"}],
            model="gpt-4",
        )
    assert isinstance(result, AgentLlmResponse)
    assert result.content == "ok"
    mock_proxy.chat_completion.assert_awaited_once()


@pytest.mark.asyncio
async def test_stream_accumulates_tool_call_fragments(facade: AgentLlmFacade) -> None:
    async def _chunks():
        yield GatewayStreamChunk(
            tool_calls=[
                {
                    "index": 0,
                    "id": "call_1",
                    "function": {"name": "read_file", "arguments": '{"path":'},
                }
            ],
        )
        yield GatewayStreamChunk(
            tool_calls=[{"index": 0, "function": {"arguments": ' "/tmp"}'}}],
        )
        yield GatewayStreamChunk(finish_reason="stop")

    facade._gateway_proxy.chat_completion = AsyncMock(return_value=_chunks())
    with patch_bridge_identity():
        stream = await facade.chat(
            messages=[{"role": "user", "content": "read"}],
            model="gpt-4",
            stream=True,
        )
        chunks: list = []
        async for chunk in stream:  # type: ignore[union-attr]
            chunks.append(chunk)
    assert chunks[-1].finish_reason == "stop"
    merged = chunks[-1].tool_calls
    assert merged is not None
    assert merged[0]["name"] == "read_file"
    assert "/tmp" in merged[0]["arguments"]


@pytest.mark.asyncio
async def test_chat_parses_tool_calls(facade: AgentLlmFacade) -> None:
    facade._gateway_proxy.chat_completion = AsyncMock(
        return_value=GatewayResponse(
            content="",
            tool_calls=[
                {
                    "id": "call_123",
                    "type": "function",
                    "function": {
                        "name": "read_file",
                        "arguments": '{"path": "/tmp/test.txt"}',
                    },
                }
            ],
            model="gpt-4",
        )
    )
    with patch_bridge_identity():
        result = await facade.chat(
            messages=[{"role": "user", "content": "Read the file"}],
            model="gpt-4",
        )
    assert result.tool_calls is not None
    assert result.tool_calls[0].name == "read_file"


@pytest.mark.asyncio
async def test_chat_proxy_error_propagates(facade: AgentLlmFacade) -> None:
    facade._gateway_proxy.chat_completion = AsyncMock(side_effect=RuntimeError("API Error"))
    with patch_bridge_identity(), pytest.raises(RuntimeError, match="API Error"):
        await facade.chat(messages=[{"role": "user", "content": "Hi"}], model="gpt-4")


@pytest.mark.asyncio
async def test_bridge_failure_when_no_user_id(facade: AgentLlmFacade) -> None:
    with patch(
        "domains.agent.infrastructure.llm.agent_llm_facade.resolve_internal_gateway_user_id",
        return_value=None,
    ), pytest.raises(RuntimeError, match="内部桥接"):
        await facade.chat(messages=[{"role": "user", "content": "hi"}], model="gpt-4")
