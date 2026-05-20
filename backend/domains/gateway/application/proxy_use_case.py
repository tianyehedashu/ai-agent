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

from contextlib import suppress
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any
import uuid

from domains.gateway.application.anthropic_native_adapt import (
    estimate_anthropic_request_tokens,
    validate_anthropic_messages_body,
)
from domains.gateway.application.budget_service import (
    PERIOD_DAILY,
    PERIOD_MONTHLY,
    PERIOD_TOTAL,
    BudgetService,
)
from domains.gateway.application.entitlement_guard import (
    EntitlementContext,
    EntitlementGuard,
)
from domains.gateway.application.model_or_route_resolution import (
    resolve_model_or_route,
)
from domains.gateway.application.prompt_cache_middleware import get_prompt_cache_middleware
from domains.gateway.application.proxy_chat_pipeline import (
    invoke_litellm_with_direct_fallback,
    prepare_chat_proxy_request,
)
from domains.gateway.application.proxy_litellm_client import ProxyLiteLLMClient
from domains.gateway.application.proxy_metadata_builder import ProxyMetadataBuilder
from domains.gateway.application.proxy_response_adapter import (
    adapt_anthropic_response,
    adapt_anthropic_stream,
    adapt_response,
    adapt_stream,
    pricing_kwargs_from_litellm,
    schedule_settle_usage,
)
from domains.gateway.application.quota_plan_service import get_quota_plan_service
from domains.gateway.application.upstream_adapter import UpstreamAdapter
from domains.gateway.domain.errors import (
    BudgetExceededError,
    EntitlementPlanExhaustedError,
)
from domains.gateway.domain.proxy_policy import (
    assert_capability_allowed,
    assert_model_allowed,
    assert_registered_model_capability,
    budget_scope_targets,
    build_budget_check_plan,
    first_present_limit,
    rate_limit_target,
)
from domains.gateway.domain.quota_plan import PlanQuotaSpec, QuotaPlanReservation
from domains.gateway.domain.types import (
    GatewayCapability,
    GatewayInboundVia,
    VirtualKeyPrincipal,
)
from domains.gateway.infrastructure.repositories.budget_repository import BudgetRepository
from domains.gateway.infrastructure.router_singleton import get_router
from utils.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


BudgetReservation = tuple[str, str | None, str, str | None]


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


class ProxyUseCase:
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

    **Application 内部协作 API**：以下 ``_``-前缀方法仅供 ``proxy_chat_pipeline``
    与 ``proxy_stream_settlement`` 复用，禁止跨 application 或在
    presentation / domain 层直接调用：

    - 校验：``_check_model`` / ``_check_capability`` /
      ``_assert_request_capability_matches_model``
    - 限流与预算：``_check_limits`` / ``_check_budget`` / ``_check_entitlement``
    - 释放：``_release_budget_reservations`` / ``_release_entitlement_reservations``
    - LiteLLM 调用：``_prepare_litellm_kwargs`` /
      ``_should_use_internal_direct_litellm`` / ``_is_router_model_miss``

    重构这些方法时务必同步更新 ``proxy_chat_pipeline`` 与 ``proxy_stream_settlement``。
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
        self._metadata_builder = ProxyMetadataBuilder(session)
        self._litellm = ProxyLiteLLMClient(session)
        self._upstream_adapter = UpstreamAdapter()
        self._prompt_cache = get_prompt_cache_middleware()

    # ---------------------------------------------------------------------
    # 校验
    # ---------------------------------------------------------------------

    def _check_model(self, model: str, ctx: ProxyContext) -> None:
        allowed_models = ctx.allowed_models or (ctx.vkey.allowed_models if ctx.vkey else ())
        assert_model_allowed(model, allowed_models)

    def _check_capability(self, ctx: ProxyContext) -> None:
        allowed_capabilities = ctx.allowed_capabilities or (
            ctx.vkey.allowed_capabilities if ctx.vkey else ()
        )
        assert_capability_allowed(ctx.capability, allowed_capabilities)

    async def _assert_request_capability_matches_model(
        self,
        ctx: ProxyContext,
        model: str,
    ) -> None:
        """注册别名或路由主选 ``GatewayModel.capability`` 须与当前 HTTP 入口一致。"""
        name = model.strip()
        if not name:
            return
        resolved = await resolve_model_or_route(self._session, ctx.team_id, name)
        if resolved is None:
            return
        assert_registered_model_capability(
            model_name=name,
            requested=ctx.capability,
            registered_capability=str(resolved.record.capability),
            via_route=resolved.route is not None,
        )

    async def _check_limits(self, ctx: ProxyContext, estimate_tokens: int = 0) -> None:
        """vkey + team 维度限流"""
        if ctx.rpm_limit is not None or ctx.tpm_limit is not None:
            target = rate_limit_target(
                vkey_id=ctx.vkey.vkey_id if ctx.vkey is not None else None,
                platform_api_key_grant_id=ctx.platform_api_key_grant_id,
                platform_api_key_id=ctx.platform_api_key_id,
            )
            if target is None:
                return
            rate_scope, rate_scope_id = target
            await self._budget.check_rate_limit(
                scope=rate_scope,
                scope_id=rate_scope_id,
                rpm_limit=ctx.rpm_limit,
                tpm_limit=ctx.tpm_limit,
                estimate_tokens=estimate_tokens,
            )
        elif ctx.vkey is not None:
            await self._budget.check_rate_limit(
                scope="vkey",
                scope_id=str(ctx.vkey.vkey_id),
                rpm_limit=ctx.vkey.rpm_limit,
                tpm_limit=ctx.vkey.tpm_limit,
                estimate_tokens=estimate_tokens,
            )
        # team 维度（从团队设置中读 rpm/tpm，简化：通过 GatewayBudget 表表示）

    async def _release_budget_reservations(self, reservations: list[BudgetReservation]) -> None:
        for scope, scope_id, period, budget_model_name in reservations:
            with suppress(Exception):
                await self._budget.release(
                    scope=scope,
                    scope_id=scope_id,
                    period=period,
                    budget_model_name=budget_model_name,
                )

    async def _release_entitlement_reservations(self, ctx: ProxyContext) -> None:
        state = ctx.entitlement_state
        if state is None or not state.reservations:
            return
        with suppress(Exception):
            await self._entitlement_guard.release(state.plan_id, state.reservations)
        ctx.entitlement_state = None

    async def _check_entitlement(
        self, ctx: ProxyContext, model: str | None, *, estimate_tokens: int = 0
    ) -> None:
        """根据 ctx (vkey_id 或 apikey_grant_id) 解析活跃 entitlement plan 并预扣。

        无匹配 plan = 默认放行；命中但任一桶耗尽抛 ``EntitlementPlanExhaustedError``。
        """
        ent_ctx = EntitlementContext(
            vkey_id=ctx.vkey.vkey_id if ctx.vkey is not None else None,
            apikey_grant_id=ctx.platform_api_key_grant_id,
            virtual_model=model,
            capability=ctx.capability.value if ctx.capability is not None else None,
        )
        result = await self._entitlement_guard.check_and_reserve(
            ent_ctx, estimate_tokens=estimate_tokens
        )
        if result.plan_id is None:
            ctx.entitlement_state = None
            return
        ctx.entitlement_state = EntitlementReservationState(
            plan_id=result.plan_id,
            plan_label=result.plan_label,
            specs=result.specs,
            reservations=result.reservations,
        )

    async def _check_budget(self, ctx: ProxyContext) -> list[BudgetReservation]:
        """按 ``BudgetCheckPlan`` 顺序扫描 team/user/key 维度预算。

        预算扫描坐标的纯逻辑（哪些 scope×period×model_key 该查）由
        ``domains.gateway.domain.proxy_policy.build_budget_check_plan`` 决定，本方法
        只负责按计划查仓储、调用 ``BudgetService``、抛错与累积请求级预扣。
        """
        repo = BudgetRepository(self._session)
        targets = budget_scope_targets(
            team_id=ctx.team_id,
            user_id=ctx.user_id,
            vkey_id=ctx.vkey.vkey_id if ctx.vkey else None,
        )
        plan = build_budget_check_plan(
            targets=targets,
            periods=(PERIOD_DAILY, PERIOD_MONTHLY, PERIOD_TOTAL),
            request_model=ctx.budget_model,
        )

        reservations: list[BudgetReservation] = []
        for query in plan:
            budget = await repo.get_for(
                query.scope, query.scope_id, query.period, model_name=query.model_name
            )
            if budget is None:
                continue
            scope_id_str = str(query.scope_id)
            check = await self._budget.check_budget(
                scope=query.scope,
                scope_id=scope_id_str,
                period=query.period,
                limit_usd=budget.limit_usd,
                limit_tokens=budget.limit_tokens,
                limit_requests=budget.limit_requests,
                budget_model_name=budget.model_name,
            )
            if not check.allowed:
                await self._release_budget_reservations(reservations)
                raise BudgetExceededError(
                    scope=query.scope,
                    period=query.period,
                    limit=float(
                        first_present_limit(
                            (
                                budget.limit_usd,
                                budget.limit_tokens,
                                budget.limit_requests,
                            )
                        )
                    ),
                    used=float(
                        check.used_usd
                        if check.reason == "usd"
                        else check.used_tokens
                        if check.reason == "tokens"
                        else check.used_requests
                    ),
                )
            if budget.limit_requests:
                try:
                    await self._budget.reserve(
                        scope=query.scope,
                        scope_id=scope_id_str,
                        period=query.period,
                        limit_requests=budget.limit_requests,
                        budget_model_name=budget.model_name,
                    )
                except Exception:
                    await self._release_budget_reservations(reservations)
                    raise
                reservations.append((query.scope, scope_id_str, query.period, budget.model_name))
        return reservations

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

    async def _prepare_litellm_kwargs(
        self,
        ctx: ProxyContext,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        prepared = await self._metadata_builder.prepare_litellm_kwargs(ctx, body)
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

    async def _should_use_internal_direct_litellm(self, ctx: ProxyContext, model: str) -> bool:
        return await self._litellm.should_use_internal_direct_litellm(ctx, model)

    @staticmethod
    def _is_router_model_miss(exc: Exception) -> bool:
        return ProxyLiteLLMClient.is_router_model_miss(exc)

    async def _direct_chat_completion(self, kwargs: dict[str, Any]) -> Any:
        return await self._litellm.direct_chat_completion(kwargs)

    async def _direct_embedding(self, kwargs: dict[str, Any]) -> Any:
        return await self._litellm.direct_embedding(kwargs)

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

        response = await invoke_litellm_with_direct_fallback(
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

        response = await invoke_litellm_with_direct_fallback(
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
        self._check_model(model, ctx)
        self._check_capability(ctx)
        await self._assert_request_capability_matches_model(ctx, model)

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
        try:
            counted = token_counter(
                model=model,
                messages=messages,
                system=system,
            )
            if isinstance(counted, int) and counted > 0:
                return counted
        except Exception:
            pass
        return estimate_anthropic_request_tokens(body)

    async def embedding(
        self,
        ctx: ProxyContext,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        ctx.capability = GatewayCapability.EMBEDDING
        model = str(body.get("model", "")).strip()
        if not model:
            raise ValueError("model is required")
        ctx.budget_model = model
        self._check_model(model, ctx)
        self._check_capability(ctx)
        await self._check_limits(ctx)
        reservations = await self._check_budget(ctx)
        try:
            await self._check_entitlement(ctx, model)
        except EntitlementPlanExhaustedError:
            await self._release_budget_reservations(reservations)
            raise

        kwargs = await self._prepare_litellm_kwargs(ctx, body)
        meta, up_c, down_c = pricing_kwargs_from_litellm(kwargs)
        try:
            if await self._should_use_internal_direct_litellm(ctx, model):
                response = await self._direct_embedding(kwargs)
            else:
                router = await get_router(self._session)
                response = await router.aembedding(**kwargs)
        except Exception:
            await self._release_budget_reservations(reservations)
            await self._release_entitlement_reservations(ctx)
            raise
        return adapt_response(
            response,
            ctx,
            self._budget,
            self._entitlement_guard,
            metadata=meta,
            upstream_custom=up_c,
            downstream_custom=down_c,
        )

    async def image_generation(
        self,
        ctx: ProxyContext,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        ctx.capability = GatewayCapability.IMAGE
        ctx.budget_model = self._optional_body_model(body)
        if ctx.budget_model:
            self._check_model(ctx.budget_model, ctx)
        self._check_capability(ctx)
        if ctx.budget_model:
            await self._assert_request_capability_matches_model(ctx, ctx.budget_model)
        await self._check_limits(ctx)
        reservations = await self._check_budget(ctx)
        try:
            await self._check_entitlement(ctx, ctx.budget_model)
        except EntitlementPlanExhaustedError:
            await self._release_budget_reservations(reservations)
            raise
        kwargs = await self._prepare_litellm_kwargs(ctx, body)
        meta, up_c, down_c = pricing_kwargs_from_litellm(kwargs)
        try:
            router = await get_router(self._session)
            response = await router.aimage_generation(**kwargs)
        except Exception:
            await self._release_budget_reservations(reservations)
            await self._release_entitlement_reservations(ctx)
            raise
        return adapt_response(
            response,
            ctx,
            self._budget,
            self._entitlement_guard,
            metadata=meta,
            upstream_custom=up_c,
            downstream_custom=down_c,
        )

    async def audio_transcription(
        self,
        ctx: ProxyContext,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        ctx.capability = GatewayCapability.AUDIO_TRANSCRIPTION
        ctx.budget_model = self._optional_body_model(body)
        self._check_capability(ctx)
        await self._check_limits(ctx)
        reservations = await self._check_budget(ctx)
        try:
            await self._check_entitlement(ctx, ctx.budget_model)
        except EntitlementPlanExhaustedError:
            await self._release_budget_reservations(reservations)
            raise
        kwargs = await self._prepare_litellm_kwargs(ctx, body)
        meta, up_c, down_c = pricing_kwargs_from_litellm(kwargs)
        try:
            router = await get_router(self._session)
            response = await router.atranscription(**kwargs)
        except Exception:
            await self._release_budget_reservations(reservations)
            await self._release_entitlement_reservations(ctx)
            raise
        return adapt_response(
            response,
            ctx,
            self._budget,
            self._entitlement_guard,
            metadata=meta,
            upstream_custom=up_c,
            downstream_custom=down_c,
        )

    async def audio_speech(
        self,
        ctx: ProxyContext,
        body: dict[str, Any],
    ) -> dict[str, Any] | bytes:
        ctx.capability = GatewayCapability.AUDIO_SPEECH
        ctx.budget_model = self._optional_body_model(body)
        self._check_capability(ctx)
        await self._check_limits(ctx)
        reservations = await self._check_budget(ctx)
        try:
            await self._check_entitlement(ctx, ctx.budget_model)
        except EntitlementPlanExhaustedError:
            await self._release_budget_reservations(reservations)
            raise
        kwargs = await self._prepare_litellm_kwargs(ctx, body)
        # 使用全局 litellm.aspeech 因为 Router 不一定暴露 aspeech
        from litellm import aspeech

        try:
            result = await aspeech(**kwargs)
        except Exception:
            await self._release_budget_reservations(reservations)
            await self._release_entitlement_reservations(ctx)
            raise
        # TTS 多为二进制返回，无 usage；仍结算请求/占位 token 与 DB 用量，与 limit_requests 预扣对齐
        schedule_settle_usage(
            ctx,
            self._budget,
            tokens=0,
            cost=Decimal("0"),
            requests=1,
            entitlement_guard=self._entitlement_guard,
        )
        return result

    async def rerank(
        self,
        ctx: ProxyContext,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        ctx.capability = GatewayCapability.RERANK
        ctx.budget_model = self._optional_body_model(body)
        self._check_capability(ctx)
        await self._check_limits(ctx)
        reservations = await self._check_budget(ctx)
        try:
            await self._check_entitlement(ctx, ctx.budget_model)
        except EntitlementPlanExhaustedError:
            await self._release_budget_reservations(reservations)
            raise
        kwargs = await self._prepare_litellm_kwargs(ctx, body)
        meta, up_c, down_c = pricing_kwargs_from_litellm(kwargs)
        from litellm import arerank

        try:
            response = await arerank(**kwargs)
        except Exception:
            await self._release_budget_reservations(reservations)
            await self._release_entitlement_reservations(ctx)
            raise
        return adapt_response(
            response,
            ctx,
            self._budget,
            self._entitlement_guard,
            metadata=meta,
            upstream_custom=up_c,
            downstream_custom=down_c,
        )

    async def moderation(
        self,
        ctx: ProxyContext,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        """处理 ``POST /v1/moderations``（经 LiteLLM ``amoderation``）。"""
        ctx.capability = GatewayCapability.MODERATION
        raw_model = body.get("model")
        model = str(raw_model).strip() if raw_model is not None else ""
        ctx.budget_model = model or None
        if model:
            self._check_model(model, ctx)
        self._check_capability(ctx)
        await self._check_limits(ctx)
        reservations = await self._check_budget(ctx)
        try:
            await self._check_entitlement(ctx, ctx.budget_model)
        except EntitlementPlanExhaustedError:
            await self._release_budget_reservations(reservations)
            raise
        kwargs = await self._prepare_litellm_kwargs(ctx, body)
        meta, up_c, down_c = pricing_kwargs_from_litellm(kwargs)
        from litellm import amoderation

        try:
            response = await amoderation(**kwargs)
        except Exception:
            await self._release_budget_reservations(reservations)
            await self._release_entitlement_reservations(ctx)
            raise
        return adapt_response(
            response,
            ctx,
            self._budget,
            self._entitlement_guard,
            metadata=meta,
            upstream_custom=up_c,
            downstream_custom=down_c,
        )

    async def video_generation(
        self,
        ctx: ProxyContext,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        """处理 ``POST /v1/videos``（经 LiteLLM ``avideo_generation``）。"""
        ctx.capability = GatewayCapability.VIDEO_GENERATION
        model = str(body.get("model", "")).strip()
        if not model:
            raise ValueError("model is required")
        ctx.budget_model = model
        self._check_model(model, ctx)
        self._check_capability(ctx)
        await self._assert_request_capability_matches_model(ctx, model)
        await self._check_limits(ctx)
        reservations = await self._check_budget(ctx)
        try:
            await self._check_entitlement(ctx, model)
        except EntitlementPlanExhaustedError:
            await self._release_budget_reservations(reservations)
            raise
        kwargs = await self._prepare_litellm_kwargs(ctx, body)
        meta, up_c, down_c = pricing_kwargs_from_litellm(kwargs)
        from litellm import avideo_generation

        try:
            response = await avideo_generation(**kwargs)
        except Exception:
            await self._release_budget_reservations(reservations)
            await self._release_entitlement_reservations(ctx)
            raise
        return adapt_response(
            response,
            ctx,
            self._budget,
            self._entitlement_guard,
            metadata=meta,
            upstream_custom=up_c,
            downstream_custom=down_c,
        )


__all__ = [
    "ProxyContext",
    "ProxyUseCase",
]
