"""
Gateway Proxy Protocol - AI Gateway 代理协议

定义跨域使用 AI Gateway 的抽象接口，避免 agent/session/studio 等域
直接依赖 gateway 域的具体实现。

设计原则（与 libs/llm/protocol.py 对齐）：
- 这是结构化类型（Protocol），任何实现这些方法的类都兼容
- 不暴露 LiteLLM 内部对象，只用基础类型与本协议自有 dataclass
- 由 gateway 域的 ProxyUseCase 实现
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from decimal import Decimal
    import uuid


@dataclass
class GatewayCallContext:
    """Gateway 调用上下文

    用于内部模块调用 Gateway 时携带身份与团队信息，桥接层据此选择
    正确的 system vkey 与 personal team 进行归账。

    Attributes:
        user_id: 归因用注册用户 UUID；通常来自 PermissionContext。无登录态时
            可由 ``resolve_internal_gateway_user_id`` 使用配置项
            ``gateway_internal_proxy_delegate_user_id`` 得到委派 ID。
        team_id: 显式指定的团队 ID；为空则使用 user 的 personal team
        capability: 调用能力（chat/embedding/...）
        metadata: 任意业务元数据，会原样写入日志便于排查
        request_id: 客户端传入的 request_id（可选，用于跨服务关联）
        store_full_messages: 是否在日志中保存完整 prompt/response（覆盖 vkey 默认）
    """

    user_id: uuid.UUID
    team_id: uuid.UUID | None = None
    capability: str = "chat"
    metadata: dict[str, Any] = field(default_factory=dict)
    request_id: str | None = None
    store_full_messages: bool | None = None


@dataclass
class GatewayResponse:
    """非流式响应（不依赖 LiteLLM 对象）"""

    content: str | None
    reasoning_content: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    finish_reason: str | None = None
    usage: dict[str, int] | None = None
    cost_usd: Decimal | None = None
    model: str | None = None
    cache_hit: bool = False
    raw: dict[str, Any] | None = None


@dataclass
class GatewayStreamChunk:
    """流式响应分片"""

    content: str | None = None
    reasoning_content: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    finish_reason: str | None = None
    usage: dict[str, int] | None = None  # 仅末帧填充


class GatewayProxyProtocol(Protocol):
    """Gateway 代理协议

    跨域调用入口。所有内部模块（chat/agent/product-info/video 等）应通过
    依赖注入获取此协议实现，而不是直接 import gateway 域。
    """

    async def chat_completion(
        self,
        messages: list[dict[str, Any]],
        *,
        ctx: GatewayCallContext,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        stream: bool = False,
        response_format: dict[str, Any] | None = None,
        api_key: str | None = None,
        api_base: str | None = None,
        **kwargs: Any,
    ) -> GatewayResponse | AsyncGenerator[GatewayStreamChunk, None]:
        """chat 调用入口（对应 OpenAI /v1/chat/completions）"""
        ...

    async def embedding(
        self,
        inputs: str | list[str],
        *,
        ctx: GatewayCallContext,
        model: str | None = None,
        api_key: str | None = None,
        api_base: str | None = None,
        **kwargs: Any,
    ) -> list[list[float]]:
        """embedding 调用入口"""
        ...

    async def count_tokens(self, text: str, model: str | None = None) -> int:
        """token 计数"""
        ...


__all__ = [
    "GatewayCallContext",
    "GatewayProxyProtocol",
    "GatewayResponse",
    "GatewayStreamChunk",
]
