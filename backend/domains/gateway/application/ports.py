"""
Gateway 应用端口 — 内部桥接与跨域调用的抽象

与 ``domains.session.application.ports`` 一致：由 **gateway 域** 声明协议与 DTO，
其它域（agent 等）依赖本模块类型，具体实现见 ``internal_bridge``。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from domains.gateway.domain.litellm.litellm_capability_mapping import LitellmModelInfoHints

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from decimal import Decimal
    import uuid


@dataclass(frozen=True)
class InvocationOverrides:
    """单次内部桥接调用的可选参数覆盖（由 Agent Chat 等消费方设置）。"""

    temperature: float | None = None
    thinking_enabled: bool | None = None


@dataclass
class GatewayCallContext:
    """内部模块经 ``GatewayBridge`` 调用 Gateway 时的上下文。

    Attributes:
        user_id: **Actor**（操作者）— 写入日志 ``gateway_user_id`` 的注册用户 UUID。
        team_id: **计费团队**（BillingTeam）— 与 ``gateway_request_logs.team_id``、
            LiteLLM metadata ``gateway_team_id`` 一致；可为 **personal 或 shared** 团队的
            ``Team.id``。若为 ``None``，``GatewayBridge`` 对该用户执行 ``ensure_personal_team``
            后归账到其 personal team。
        capability: 调用能力（chat/embedding/...）
        metadata: 任意业务元数据，会原样写入日志便于排查
        request_id: 客户端传入的 request_id（可选，用于跨服务关联）
        store_full_messages: 是否在日志中保存完整 prompt/response（覆盖 vkey 默认）

    注意：HTTP 查询 ``usage_aggregation``（管理面读模型，产品文案"团队/我"）**不**在此类型
    中表达；其仅影响 ``GET /dashboard/summary`` 等聚合接口的切片方式。
    """

    user_id: uuid.UUID
    team_id: uuid.UUID | None = None
    capability: str = "chat"
    metadata: dict[str, Any] = field(default_factory=dict)
    request_id: str | None = None
    store_full_messages: bool | None = None
    invocation_overrides: InvocationOverrides | None = None
    """可选：覆盖温度 / 思考开关；出站前由 Bridge 合并，再经 ``UpstreamAdapter`` 应用领域策略。"""


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


class LitellmCapabilityHintPort(Protocol):
    """查询 LiteLLM 内置价目表中的能力标记（catalog 写侧 / 探测 enrich）。"""

    def get_model_hints(self, *, provider: str, real_model: str) -> LitellmModelInfoHints | None:
        """已映射模型返回 hint 子集；未映射或 litellm 不可用返回 None。"""

    def supports_reasoning(self, *, provider: str, real_model: str) -> bool | None:
        """已映射且支持 reasoning 返回 True/False；未映射返回 None。"""


class GatewayProxyProtocol(Protocol):
    """Gateway 代理协议

    跨域调用入口。所有内部模块（chat/agent/listing-studio/video 等）应通过
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
        **kwargs: Any,
    ) -> list[list[float]]:
        """embedding 调用入口"""
        ...

    async def video_generation(
        self,
        prompt: str,
        *,
        ctx: GatewayCallContext,
        model: str,
        seconds: int | None = None,
        reference_image_urls: list[str] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """视频生成调用入口（对应 OpenAI /v1/videos）。

        返回 OpenAI 兼容响应 dict（含 ``id`` / ``status`` / ``video.url`` 等）。
        LiteLLM ``avideo_generation`` 为同步阻塞调用（默认 600s），由调用方决定
        是否在后台 task 中等待。
        """
        ...

    async def count_tokens(self, text: str, model: str | None = None) -> int:
        """token 计数"""
        ...


class ListingStudioLocalImagePort(Protocol):
    """解析 listing-studio 本地存储图片路径（由 Agent 域在 bootstrap 注入实现）。"""

    async def resolve_local_image_path(self, filename: str) -> Path | None:
        """本地模式返回可读路径；非 local 或文件不存在时返回 None。"""
        ...


ListingStudioLocalImagePortFactory = Callable[[AsyncSession], ListingStudioLocalImagePort]


class VirtualKeyGrantLifecyclePort(Protocol):
    """vkey 跨团队授权生命周期（tenancy 成员变更 / 团队删除时同步撤销）。"""

    async def revoke_for_membership_lost(
        self,
        *,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> int:
        """用户失去 team membership 时撤销其在该 team 上的非自洽 grant。"""
        ...

    async def revoke_for_team_deleted(self, *, tenant_id: uuid.UUID) -> int:
        """团队删除前撤销所有指向该 team 的 grant。"""
        ...


class RouteGrantLifecyclePort(Protocol):
    """路由跨团队共享授权生命周期（tenancy 成员变更 / 团队删除时同步撤销）。"""

    async def revoke_for_membership_lost(
        self,
        *,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> int:
        """用户失去 team membership 时撤销其共享进该 team 的路由 grant。"""
        ...

    async def revoke_for_team_deleted(self, *, tenant_id: uuid.UUID) -> int:
        """团队删除前撤销所有指向该 team 的路由 grant。"""
        ...


__all__ = [
    "GatewayCallContext",
    "GatewayProxyProtocol",
    "GatewayResponse",
    "GatewayStreamChunk",
    "InvocationOverrides",
    "ListingStudioLocalImagePort",
    "ListingStudioLocalImagePortFactory",
    "LitellmCapabilityHintPort",
    "RouteGrantLifecyclePort",
    "VirtualKeyGrantLifecyclePort",
]
