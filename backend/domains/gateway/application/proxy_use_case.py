"""
ProxyUseCase - 网关调用编排

流水线：
1. 鉴权（由 deps 完成，传入 GatewayPrincipal / VkeyOrApikeyPrincipal）
2. 校验模型/能力白名单
3. 限流（vkey/team/user 维度）
4. 预算预扣（请求计数）
5. 拼装 metadata 注入到 LiteLLM 调用
6. 调用 Router（acompletion / aembedding / aimage_generation / atranscription / aspeech / arerank）
7. 结算（commit token & cost）
8. 返回响应（OpenAI 兼容字典）
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
import uuid

from domains.gateway.application.anthropic_native_adapt import (
    estimate_anthropic_request_tokens,
    validate_anthropic_messages_body,
)
from domains.gateway.application.budget_service import BudgetService
from domains.gateway.application.entitlement_guard import EntitlementGuard
from domains.gateway.application.prompt_cache_middleware import get_prompt_cache_middleware
from domains.gateway.application.proxy_chat_pipeline import prepare_chat_proxy_request
from domains.gateway.application.proxy_guard import (
    ProxyGuard,
)
from domains.gateway.application.proxy_litellm_client import ProxyLiteLLMClient
from domains.gateway.application.proxy_metadata_builder import (
    PreparedLitellmKwargs,
    ProxyMetadataBuilder,
)
from domains.gateway.application.proxy_non_chat_pipeline import ProxyNonChatMixin
from domains.gateway.application.proxy_response_adapter import (
    adapt_anthropic_response,
    adapt_anthropic_stream,
    adapt_response,
    adapt_stream,
)
from domains.gateway.application.proxy_router_invoke import invoke_router_with_direct_fallback
from domains.gateway.application.quota_plan_service import get_quota_plan_service
from domains.gateway.application.upstream_adapter import UpstreamAdapter
from domains.gateway.domain.quota_plan import PlanQuotaSpec, QuotaPlanReservation
from domains.gateway.domain.types import (
    GatewayCapability,
    GatewayInboundVia,
    VirtualKeyPrincipal,
)
from domains.gateway.infrastructure.router_singleton import get_router
from utils.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


@dataclass
class EntitlementReservationState:
    """单次调用命中的下游 entitlement 套餐预扣信息，跨 reserve / settle 阶段共享。"""

    plan_id: uuid.UUID
    plan_label: str | None
    specs: list[PlanQuotaSpec]
    reservations: list[QuotaPlanReservation]


@dataclass
class ProxyContext:
    """单次 OpenAI 兼容代理调用的上下文。

    Attributes:
        team_id: **计费团队**（BillingTeam，与日志 ``gateway_team_id``、
            ``gateway_request_logs.team_id`` 一致），为一次调用归属的租户键。
        user_id: 触发用户（可为 None，视入口而定）。
        vkey: 虚拟 Key 主体；内部 system vkey 走同字段；平台 ``sk-*`` 入站时可为 None。
        capability: 网关能力枚举。
        request_id: 关联 ID。
        store_full_messages / guardrail_enabled: 日志与护栏策略。
        budget_model: 请求体中的 ``model`` 字符串（与 ``gateway_budgets.model_name`` 对齐），
            用于模型级预算；未设置时仅校验/结算「全模型」汇总行（``model_name IS NULL``）。
        inbound_via: 入站鉴权路径 ``vkey``（``sk-gw-*``）或 ``apikey``（平台 ``sk-*`` + ``gateway:proxy``）。
        platform_api_key_id: 当 ``inbound_via=apikey`` 时为 Identity API Key 主键；否则为 ``None``。
        platform_api_key_grant_id: 当 ``inbound_via=apikey`` 时为命中的 Gateway grant 主键。

    与 ``BudgetUpsert.scope``（system/team/key/user）及 HTTP ``usage_aggregation`` 正交。
    """

    team_id: uuid.UUID
    user_id: uuid.UUID | None
    vkey: VirtualKeyPrincipal | None
    capability: GatewayCapability
    request_id: str
    store_full_messages: bool
    guardrail_enabled: bool
    budget_model: str | None = None
    inbound_via: GatewayInboundVia = "vkey"
    platform_api_key_id: uuid.UUID | None = None
    platform_api_key_grant_id: uuid.UUID | None = None
    allowed_models: tuple[str, ...] = ()
    allowed_capabilities: tuple[GatewayCapability, ...] = ()
    rpm_limit: int | None = None
    tpm_limit: int | None = None
    entitlement_state: EntitlementReservationState | None = None
    client_ua: str | None = None
    client_type: str = "unknown"


class ProxyUseCase(ProxyNonChatMixin):
    """对外 LLM 代理用例（``/v1/*`` 编排门面）。

    **公开入口**：``chat_completion`` / ``anthropic_messages`` / ``embedding`` /
    ``image_generation`` / ``audio_transcription`` / ``audio_speech`` /
    ``rerank`` / ``moderation`` / ``video_generation``。

    **职责拆分**：

    - 纯领域规则（白名单、能力匹配、预算扫描计划、限流目标选择）→
      ``domains.gateway.domain.proxy_policy``。
    - Metadata / 归因 / 下游定价注入 → ``ProxyMetadataBuilder``
      （``proxy_metadata_builder``）。
    - LiteLLM Router / 内部直连 → ``ProxyLiteLLMClient`` （``proxy_litellm_client``）。
    - 响应适配、成本计算、预算/套餐结算 → ``proxy_response_adapter``。
    - 后台 fire-and-forget 结算任务收口 → ``proxy_deferred_tasks``。

    **入站护栏**：模型/能力校验、限流、预算、entitlement 预扣全部由
    :class:`ProxyGuard` （``proxy_guard``）提供公开 API；本类内部与
    ``proxy_chat_pipeline`` 都通过 :attr:`guard` 访问，**禁止**再为这些行为新增
    ``_``-前缀方法。

    **下游 LiteLLM 调用助手**（``_prepare_litellm_kwargs`` /
    ``_should_use_internal_direct_litellm`` / ``_is_router_model_miss``）仅供
    ``proxy_chat_pipeline`` / ``proxy_stream_settlement`` 复用，重构时同步更新。
    """

    def __init__(
        self,
        session: AsyncSession,
        *,
        budget_service: BudgetService | None = None,
        entitlement_guard: EntitlementGuard | None = None,
    ) -> None:
        self._session = session
        self._budget = budget_service or BudgetService()
        self._entitlement_guard = entitlement_guard or EntitlementGuard(
            session, quota_service=get_quota_plan_service()
        )
        self._guard = ProxyGuard(session, self._budget, self._entitlement_guard)
        self._metadata_builder = ProxyMetadataBuilder(session)
        self._litellm = ProxyLiteLLMClient(session)
        self._upstream_adapter = UpstreamAdapter()
        self._prompt_cache = get_prompt_cache_middleware()

    @property
    def guard(self) -> ProxyGuard:
        """入站护栏服务（公开访问点；供 ``proxy_chat_pipeline`` 与测试注入）。"""
        return self._guard

    @property
    def budget_service(self) -> BudgetService:
        """供 ``proxy_response_adapter`` 等内部协作模块只读访问预算结算句柄。"""
        return self._budget

    @property
    def entitlement_guard(self) -> EntitlementGuard:
        """供 ``proxy_response_adapter`` 等内部协作模块只读访问 entitlement 句柄。"""
        return self._entitlement_guard

    @staticmethod
    def _optional_body_model(body: dict[str, Any]) -> str | None:
        raw = body.get("model")
        if raw is None:
            return None
        s = str(raw).strip()
        return s or None

    # ---------------------------------------------------------------------
    # Metadata 注入
    # ---------------------------------------------------------------------

    async def _credential_metadata_for_virtual_model(
        self, team_id: uuid.UUID, virtual_model: str | None
    ) -> dict[str, Any]:
        return await self._metadata_builder.credential_metadata_for_virtual_model(
            team_id, virtual_model
        )

    async def _build_metadata(
        self,
        ctx: ProxyContext,
        *,
        user_kwargs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self._metadata_builder.build(ctx, user_kwargs=user_kwargs)

    def _kwargs_from_prepared(self, prepared: PreparedLitellmKwargs) -> dict[str, Any]:
        resolved = prepared.resolved
        tags = resolved.record.tags if resolved is not None else None
        tag_dict = tags if isinstance(tags, dict) else None
        kwargs = self._upstream_adapter.adapt(
            prepared.kwargs,
            client_model=prepared.client_model,
            resolved=resolved,
        )
        return self._prompt_cache.inbound(
            kwargs,
            model=prepared.client_model or str(kwargs.get("model", "")),
            tags=tag_dict,
        )

    async def _prepare_litellm_kwargs(
        self,
        ctx: ProxyContext,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        prepared = await self._metadata_builder.prepare_litellm_kwargs(ctx, body)
        return self._kwargs_from_prepared(prepared)

    async def _should_use_internal_direct_litellm(self, ctx: ProxyContext, model: str) -> bool:
        return await self._litellm.should_use_internal_direct_litellm(ctx, model)

    @staticmethod
    def _is_router_model_miss(exc: Exception) -> bool:
        return ProxyLiteLLMClient.is_router_model_miss(exc)

    async def _direct_chat_completion(self, kwargs: dict[str, Any]) -> Any:
        return await self._litellm.direct_chat_completion(kwargs)

    async def _direct_embedding(self, kwargs: dict[str, Any]) -> Any:
        return await self._litellm.direct_embedding(kwargs)

    async def _dashscope_direct_embedding(
        self,
        ctx: ProxyContext,
        client_model: str,
        kwargs: dict[str, Any],
        *,
        real_model: str | None = None,
    ) -> dict[str, Any]:
        return await self._litellm.dashscope_direct_embedding(
            ctx, client_model, kwargs, real_model=real_model
        )

    async def _merge_direct_deployment_litellm_params(
        self,
        kwargs: dict[str, Any],
        ctx: ProxyContext,
        virtual_model: str,
    ) -> dict[str, Any]:
        return await self._litellm.merge_direct_deployment_litellm_params(
            kwargs, ctx, virtual_model
        )

    async def _direct_anthropic_messages(self, kwargs: dict[str, Any]) -> Any:
        return await self._litellm.direct_anthropic_messages(kwargs)

    async def _router_anthropic_messages(self, kwargs: dict[str, Any]) -> Any:
        return await self._litellm.router_anthropic_messages(kwargs)

    async def _direct_speech(self, kwargs: dict[str, Any]) -> Any:
        return await self._litellm.direct_speech(kwargs)

    async def _router_speech(self, kwargs: dict[str, Any]) -> Any:
        return await self._litellm.router_speech(kwargs)

    async def _direct_rerank(self, kwargs: dict[str, Any]) -> Any:
        return await self._litellm.direct_rerank(kwargs)

    async def _router_rerank(self, kwargs: dict[str, Any]) -> Any:
        return await self._litellm.router_rerank(kwargs)

    async def _direct_moderation(self, kwargs: dict[str, Any]) -> Any:
        return await self._litellm.direct_moderation(kwargs)

    async def _router_moderation(self, kwargs: dict[str, Any]) -> Any:
        return await self._litellm.router_moderation(kwargs)

    async def _direct_video_generation(self, kwargs: dict[str, Any]) -> Any:
        return await self._litellm.direct_video_generation(kwargs)

    async def _router_video_generation(self, kwargs: dict[str, Any]) -> Any:
        return await self._litellm.router_video_generation(kwargs)

    async def _direct_image_generation(self, kwargs: dict[str, Any]) -> Any:
        return await self._litellm.direct_image_generation(kwargs)

    async def _router_image_generation(self, kwargs: dict[str, Any]) -> Any:
        return await self._litellm.router_image_generation(kwargs)

    async def _direct_transcription(self, kwargs: dict[str, Any]) -> Any:
        return await self._litellm.direct_transcription(kwargs)

    async def _router_transcription(self, kwargs: dict[str, Any]) -> Any:
        return await self._litellm.router_transcription(kwargs)

    # ---------------------------------------------------------------------
    # 主入口
    # ---------------------------------------------------------------------

    async def chat_completion(
        self,
        ctx: ProxyContext,
        body: dict[str, Any],
    ) -> dict[str, Any] | AsyncIterator[dict[str, Any]]:
        """处理 /v1/chat/completions"""
        estimate_tokens = sum(
            len(str(m.get("content", ""))) for m in (body.get("messages") or [])
        ) // 4 + int(body.get("max_tokens") or 0)
        prepared = await prepare_chat_proxy_request(
            self,
            ctx,
            body,
            estimate_tokens=estimate_tokens,
            require_model=True,
        )
        use_direct = await self._should_use_internal_direct_litellm(ctx, prepared.model)

        async def _direct() -> Any:
            return await self._direct_chat_completion(prepared.kwargs)

        async def _router() -> Any:
            router = await get_router(self._session)
            return await router.acompletion(**prepared.kwargs)

        response = await invoke_router_with_direct_fallback(
            self,
            ctx,
            prepared.model,
            prepared.reservations,
            use_direct=use_direct,
            direct_call=_direct,
            router_call=_router,
        )
        if prepared.stream:
            return adapt_stream(
                response,
                ctx,
                self._budget,
                self._entitlement_guard,
                metadata=prepared.metadata,
                downstream_custom=prepared.downstream_custom,
            )
        return adapt_response(
            response,
            ctx,
            self._budget,
            self._entitlement_guard,
            metadata=prepared.metadata,
            upstream_custom=prepared.upstream_custom,
            downstream_custom=prepared.downstream_custom,
        )

    async def anthropic_messages(
        self,
        ctx: ProxyContext,
        body: dict[str, Any],
    ) -> dict[str, Any] | AsyncIterator[bytes]:
        """处理 ``POST /v1/messages``（LiteLLM Anthropic 原生通道）。"""
        prepared = await prepare_chat_proxy_request(
            self,
            ctx,
            body,
            estimate_tokens=estimate_anthropic_request_tokens(body),
            require_model=False,
            body_validator=validate_anthropic_messages_body,
        )
        use_direct = await self._should_use_internal_direct_litellm(ctx, prepared.model)

        async def _direct() -> Any:
            direct_kw = await self._merge_direct_deployment_litellm_params(
                prepared.kwargs, ctx, prepared.model
            )
            return await self._direct_anthropic_messages(direct_kw)

        async def _router() -> Any:
            return await self._router_anthropic_messages(prepared.kwargs)

        response = await invoke_router_with_direct_fallback(
            self,
            ctx,
            prepared.model,
            prepared.reservations,
            use_direct=use_direct,
            direct_call=_direct,
            router_call=_router,
        )
        if prepared.stream:
            return adapt_anthropic_stream(
                response,
                ctx,
                self._budget,
                self._entitlement_guard,
                metadata=prepared.metadata,
                downstream_custom=prepared.downstream_custom,
            )
        return adapt_anthropic_response(
            response,
            ctx,
            self._budget,
            self._entitlement_guard,
            metadata=prepared.metadata,
            upstream_custom=prepared.upstream_custom,
            downstream_custom=prepared.downstream_custom,
        )

    async def anthropic_count_tokens(
        self,
        ctx: ProxyContext,
        body: dict[str, Any],
    ) -> dict[str, int]:
        """``POST /v1/messages/count_tokens``：不计预算/限流，仅校验模型与白名单。"""
        validate_anthropic_messages_body(body)
        ctx.capability = GatewayCapability.CHAT
        model = str(body.get("model", "")).strip()
        if not model:
            raise ValueError("model is required")
        ctx.budget_model = model
        self._guard.check_model(model, ctx)
        self._guard.check_capability(ctx)
        await self._guard.assert_request_capability_matches_model(ctx, model)

        input_tokens = await self._estimate_anthropic_input_tokens(body, model)
        return {"input_tokens": input_tokens}

    async def _estimate_anthropic_input_tokens(
        self,
        body: dict[str, Any],
        model: str,
    ) -> int:
        try:
            from litellm import token_counter
        except ImportError:
            return estimate_anthropic_request_tokens(body)

        messages = body.get("messages")
        if not isinstance(messages, list):
            return estimate_anthropic_request_tokens(body)
        system = body.get("system")
        merged_messages: list[Any] = []
        if (isinstance(system, str) and system) or isinstance(system, list):
            merged_messages.append({"role": "system", "content": system})
        merged_messages.extend(messages)
        try:
            counted = token_counter(model=model, messages=merged_messages)
            if isinstance(counted, int) and counted > 0:
                return counted
        except Exception:
            pass
        return estimate_anthropic_request_tokens(body)

__all__ = [
    "ProxyContext",
    "ProxyUseCase",
]
