"""
Gateway 应用端口 — 内部桥接与跨域调用的抽象

与 ``domains.session.application.ports`` 一致：由 **gateway 域** 声明协议与 DTO，
其它域（agent 等）依赖本模块类型，具体实现见 ``internal_bridge``。
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
    """内部模块经 ``GatewayBridge`` 调用 Gateway 时的上下文。

    Attributes:
        user_id: **Actor**（操作者）— 写入日志 ``gateway_user_id`` 的注册用户 UUID。
        team_id: **计费工作区**（BillingWorkspace）— 与 ``gateway_request_logs.team_id``、
            LiteLLM metadata ``gateway_team_id`` 一致；可为 **personal 或 shared** 工作区的
            ``Team.id``。若为 ``None``，``GatewayBridge`` 对该用户执行 ``ensure_personal_team``
            后归账到其 personal team。
        capability: 调用能力（chat/embedding/...）
        metadata: 任意业务元数据，会原样写入日志便于排查
        request_id: 客户端传入的 request_id（可选，用于跨服务关联）
        store_full_messages: 是否在日志中保存完整 prompt/response（覆盖 vkey 默认）

    注意：HTTP 查询 ``usage_aggregation``（管理面读模型）**不**在此类型中表达；其仅影响
    ``GET /dashboard/summary`` 等聚合接口的切片方式。
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
    # value 允许 dict —— provider 会在 ``prompt_tokens_details`` /
    # ``completion_tokens_details`` 下嵌入 ``cached_tokens`` / ``reasoning_tokens``
    # 子结构（OpenAI / DeepSeek-Reasoner 等）。
    usage: dict[str, Any] | None = None
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
    usage: dict[str, Any] | None = None  # 仅末帧填充（同 GatewayResponse.usage）


class GatewayProxyProtocol(Protocol):
    """Gateway 代理协议

    跨域调用入口。所有内部模块（chat/agent/product-info/video 等）应通过
    依赖注入获取此协议实现，而不是直接 import ``GatewayBridge`` 实现类。
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
