"""
LLM Mock 工具

提供 Agent LLM 门面与 Gateway 桥接端口的 Mock，用于测试。
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from domains.agent.domain.types import ToolCall
from domains.agent.infrastructure.llm.agent_llm_facade import AgentLlmResponse, AgentStreamChunk
from domains.gateway.application.ports import GatewayResponse


@dataclass
class MockLLMChunk:
    """Mock LLM 流式块"""

    content: str = ""
    tool_calls: list[ToolCall] | None = None
    finish_reason: str | None = None


class LLMMockBuilder:
    """LLM Mock 构建器"""

    def __init__(self):
        self.responses = []
        self.stream_chunks = []

    def with_text_response(self, content: str) -> "LLMMockBuilder":
        """添加文本响应"""
        self.responses.append({"type": "text", "content": content})
        return self

    def with_tool_call(
        self,
        name: str,
        arguments: dict,
        call_id: str = "call_123",
    ) -> "LLMMockBuilder":
        """添加工具调用"""
        tool_call = ToolCall(id=call_id, name=name, arguments=arguments)
        self.responses.append(
            {
                "type": "tool_call",
                "tool_call": tool_call,
            }
        )
        return self

    def with_stream(self, chunks: list[str]) -> "LLMMockBuilder":
        """添加流式块"""
        self.stream_chunks = chunks
        return self

    def build(self) -> AsyncMock:
        """构建 Mock 对象"""
        mock = AsyncMock()

        # 普通响应
        if self.responses:
            mock.chat.return_value = self._build_response()

        # 流式响应
        if self.stream_chunks:
            mock.chat_stream.return_value = self._stream_generator()

        return mock

    def _build_response(self) -> AgentLlmResponse:
        """构建响应对象"""
        if self.responses[0]["type"] == "text":
            return AgentLlmResponse(
                content=self.responses[0]["content"],
                tool_calls=None,
            )
        else:
            tool_calls = [r["tool_call"] for r in self.responses if r["type"] == "tool_call"]
            return AgentLlmResponse(
                content="",
                tool_calls=tool_calls if tool_calls else None,
            )

    async def _stream_generator(self) -> AsyncIterator[AgentStreamChunk]:
        """流式生成器"""
        for chunk in self.stream_chunks:
            yield AgentStreamChunk(content=chunk)
        yield AgentStreamChunk(finish_reason="stop")


def create_simple_response_mock(content: str) -> AsyncMock:
    """创建简单文本响应 Mock"""
    return LLMMockBuilder().with_text_response(content).build()


def create_tool_call_mock(tool_name: str, arguments: dict) -> AsyncMock:
    """创建工具调用 Mock"""
    return LLMMockBuilder().with_tool_call(tool_name, arguments).build()


class GatewayProxyMockBuilder:
    """``GatewayProxyProtocol`` Mock 构建器（Chat / Embedding 经桥接）。"""

    def __init__(self) -> None:
        self._chat_content: str | None = "mock-reply"
        self._embedding: list[list[float]] | None = [[0.0, 0.1]]

    def with_chat_content(self, content: str) -> "GatewayProxyMockBuilder":
        self._chat_content = content
        return self

    def with_embedding_rows(self, rows: list[list[float]]) -> "GatewayProxyMockBuilder":
        self._embedding = rows
        return self

    def build(self) -> MagicMock:
        proxy = MagicMock()
        proxy.chat_completion = AsyncMock(
            return_value=GatewayResponse(content=self._chat_content, model="mock"),
        )
        proxy.embedding = AsyncMock(return_value=self._embedding)
        return proxy


def create_gateway_proxy_mock(**kwargs: Any) -> MagicMock:
    """快捷创建 Gateway 桥接 Mock。"""
    b = GatewayProxyMockBuilder()
    if "content" in kwargs:
        b.with_chat_content(str(kwargs["content"]))
    if "embedding" in kwargs:
        b.with_embedding_rows(kwargs["embedding"])
    return b.build()
