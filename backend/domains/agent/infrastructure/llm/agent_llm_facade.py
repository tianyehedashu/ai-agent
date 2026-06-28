"""
Agent LLM Facade - 经 AI Gateway 内部桥接的领域 LLM 客户端

所有上游出站经 GatewayProxyProtocol；不 import litellm，不读取 provider API Key。
"""

from __future__ import annotations

from collections.abc import AsyncGenerator  # noqa: TC003 — 流式 chat 返回类型运行期使用
import json
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel
import tiktoken

from domains.agent.domain.types import Message, ToolCall
from domains.agent.infrastructure.llm.message_formatter import format_domain_messages
from domains.gateway.application.bridge.bridge_attribution import resolve_gateway_bridge_attribution
from domains.gateway.application.bridge.gateway_internal_log_context import (
    get_internal_store_full_override,
)
from domains.gateway.application.bridge.gateway_proxy_factory import get_gateway_proxy
from domains.gateway.application.bridge.internal_bridge_actor import resolve_internal_gateway_user_id
from domains.gateway.application.ports import (
    GatewayCallContext,
    GatewayResponse,
    GatewayStreamChunk,
    InvocationOverrides,
)
from libs.config.interfaces import LLMConfigProtocol  # noqa: TC001 — __init__ 运行期使用
from utils.logging import get_logger

if TYPE_CHECKING:
    from domains.agent.application.ports.model_catalog_port import ModelCatalogPort
    from domains.gateway.application.ports import GatewayProxyProtocol

logger = get_logger(__name__)


class AgentLlmResponse(BaseModel):
    """Agent 域 LLM 响应（与 GatewayResponse 解耦）。"""

    content: str | None = None
    reasoning_content: str | None = None
    tool_calls: list[ToolCall] | None = None
    finish_reason: str | None = None
    usage: dict[str, Any] | None = None
    model: str | None = None


class AgentStreamChunk(BaseModel):
    """Agent 域流式块。"""

    content: str | None = None
    reasoning_content: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    finish_reason: str | None = None
    usage: dict[str, Any] | None = None


class AgentLlmFacade:
    """Agent 侧 LLM 门面：领域消息 ↔ Gateway 桥接 ↔ Agent DTO。"""

    def __init__(
        self,
        config: LLMConfigProtocol,
        gateway_proxy: GatewayProxyProtocol | None = None,
        model_catalog: ModelCatalogPort | None = None,
    ) -> None:
        self.config = config
        self._gateway_proxy = gateway_proxy or get_gateway_proxy()
        _ = model_catalog  # 能力适配已下沉 Gateway；保留参数兼容 DI

    @staticmethod
    def _require_bridge_user_id() -> None:
        if resolve_internal_gateway_user_id() is None:
            raise RuntimeError(
                "AI Gateway 内部桥接需要已登录用户或配置 gateway_internal_proxy_delegate_user_id"
            )

    @staticmethod
    def _parse_arguments(arguments: str) -> dict[str, Any]:
        try:
            parsed = json.loads(arguments)
            return parsed if isinstance(parsed, dict) else {"raw": arguments}
        except json.JSONDecodeError:
            return {"raw": arguments}

    def _tool_calls_from_gateway(
        self,
        tool_calls_raw: list[dict[str, Any]] | None,
    ) -> list[ToolCall] | None:
        if not tool_calls_raw:
            return None
        parsed: list[ToolCall] = []
        for tc in tool_calls_raw:
            if not isinstance(tc, dict):
                continue
            fn = tc.get("function")
            if isinstance(fn, dict):
                name = str(fn.get("name", ""))
                args_raw = fn.get("arguments", "")
            else:
                name = str(tc.get("name", ""))
                args_raw = tc.get("arguments", "")
            parsed.append(
                ToolCall(
                    id=str(tc.get("id", "")),
                    name=name,
                    arguments=self._parse_arguments(str(args_raw)),
                )
            )
        return parsed or None

    def _response_from_gateway(
        self, result: GatewayResponse, model_fallback: str
    ) -> AgentLlmResponse:
        return AgentLlmResponse(
            content=result.content,
            reasoning_content=result.reasoning_content,
            tool_calls=self._tool_calls_from_gateway(result.tool_calls),
            finish_reason=result.finish_reason,
            usage=result.usage,
            model=result.model or model_fallback,
        )

    async def _invoke_gateway_chat(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str,
        temperature: float,
        max_tokens: int,
        tools: list[dict[str, Any]] | None,
        tool_choice: str | dict | None,
        stream: bool,
        response_format: dict[str, Any] | None,
        invocation_overrides: InvocationOverrides | None = None,
    ) -> AgentLlmResponse | AsyncGenerator[AgentStreamChunk, None]:
        self._require_bridge_user_id()
        attr = resolve_gateway_bridge_attribution()
        ctx = GatewayCallContext(
            user_id=attr.actor_user_id,
            team_id=attr.billing_team_id,
            capability="chat",
            store_full_messages=get_internal_store_full_override(),
            invocation_overrides=invocation_overrides,
        )
        bridge = self._gateway_proxy

        if stream:

            async def _wrap() -> AsyncGenerator[AgentStreamChunk, None]:
                tool_buffer: dict[int, dict[str, Any]] = {}
                stream_iter = await bridge.chat_completion(
                    messages,
                    ctx=ctx,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    tools=tools,
                    tool_choice=tool_choice,
                    stream=True,
                    response_format=response_format,
                )
                async for chunk in stream_iter:  # type: ignore[union-attr]
                    chunk_obj: GatewayStreamChunk = chunk
                    if chunk_obj.tool_calls:
                        for tc in chunk_obj.tool_calls:
                            if not isinstance(tc, dict):
                                continue
                            idx = int(tc.get("index", 0))
                            if idx not in tool_buffer:
                                tool_buffer[idx] = {
                                    "id": str(tc.get("id", "")),
                                    "name": "",
                                    "arguments": "",
                                }
                            fn = tc.get("function")
                            if isinstance(fn, dict):
                                if fn.get("name"):
                                    tool_buffer[idx]["name"] = str(fn["name"])
                                if fn.get("arguments"):
                                    tool_buffer[idx]["arguments"] += str(fn["arguments"])
                    yield AgentStreamChunk(
                        content=chunk_obj.content,
                        reasoning_content=chunk_obj.reasoning_content,
                        tool_calls=list(tool_buffer.values()) if tool_buffer else None,
                        finish_reason=chunk_obj.finish_reason,
                        usage=chunk_obj.usage,
                    )

            return _wrap()

        result = await bridge.chat_completion(
            messages,
            ctx=ctx,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            tool_choice=tool_choice,
            stream=False,
            response_format=response_format,
        )
        if not isinstance(result, GatewayResponse):
            raise TypeError("expected GatewayResponse from non-stream chat_completion")
        return self._response_from_gateway(result, model)

    async def chat(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict | None = None,
        stream: bool = False,
        response_format: dict[str, Any] | None = None,
        invocation_overrides: InvocationOverrides | None = None,
    ) -> AgentLlmResponse | AsyncGenerator[AgentStreamChunk, None]:
        """聊天补全（仅经 AI Gateway 桥接；凭据由 Gateway 凭据池解析）。"""
        model_name = model or self.config.default_model
        return await self._invoke_gateway_chat(
            messages=messages,
            model=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            tool_choice=tool_choice,
            stream=stream,
            response_format=response_format,
            invocation_overrides=invocation_overrides,
        )

    def format_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        return format_domain_messages(messages)

    async def count_tokens(self, text: str, model: str | None = None) -> int:
        model_name = model or self.config.default_model
        try:
            encoding = tiktoken.encoding_for_model(model_name)
        except KeyError:
            encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))

    async def embed(self, text: str, model: str | None = None) -> list[float]:
        rows = await self.embed_batch([text], model=model)
        if not rows:
            raise ValueError("Gateway embedding returned empty")
        return rows[0]

    async def embed_batch(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        if not texts:
            return []
        self._require_bridge_user_id()
        model_name = model or self.config.embedding_model
        attr = resolve_gateway_bridge_attribution()
        rows = await self._gateway_proxy.embedding(
            texts,
            ctx=GatewayCallContext(
                user_id=attr.actor_user_id,
                team_id=attr.billing_team_id,
                capability="embedding",
            ),
            model=model_name,
        )
        if not rows or any(r is None for r in rows):
            raise ValueError("Gateway embedding returned empty rows")
        return [list(r) for r in rows if r is not None]


__all__ = [
    "AgentLlmFacade",
    "AgentLlmResponse",
    "AgentStreamChunk",
]
