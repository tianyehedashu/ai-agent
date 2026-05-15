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

import asyncio
from contextlib import suppress
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any
import uuid

from bootstrap.config import settings
from domains.gateway.application.budget_service import (
    PERIOD_DAILY,
    PERIOD_MONTHLY,
    PERIOD_TOTAL,
    BudgetService,
)
from domains.gateway.application.route_snapshot_cache import get_route_snapshot_metadata
from domains.gateway.domain.errors import (
    BudgetExceededError,
    CapabilityNotAllowedError,
    GuardrailBlockedError,
    ModelNotAllowedError,
    RateLimitExceededError,
)
from domains.gateway.domain.types import (
    GatewayCapability,
    GatewayInboundVia,
    VirtualKeyPrincipal,
)
from domains.gateway.infrastructure.models.budget import GatewayBudget
from domains.gateway.infrastructure.repositories.budget_repository import BudgetRepository
from domains.gateway.infrastructure.repositories.credential_repository import (
    ProviderCredentialRepository,
)
from domains.gateway.infrastructure.repositories.model_repository import (
    GatewayModelRepository,
    GatewayRouteRepository,
)
from domains.gateway.infrastructure.router_singleton import get_router
from domains.tenancy.infrastructure.repositories.team_repository import TeamRepository
from libs.db.database import get_session_context
from utils.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, AsyncIterator

    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

# 代理侧 fire-and-forget 任务（如非流式响应后的异步结算），不进入 app.state.background_tasks。
_proxy_deferred_tasks: set[asyncio.Task[Any]] = set()


def register_proxy_deferred_task(task: asyncio.Task[Any]) -> None:
    """登记须在进程/测试 teardown 时取消并等待的代理后台任务。"""
    _proxy_deferred_tasks.add(task)

    def _done(t: asyncio.Task[Any]) -> None:
        _proxy_deferred_tasks.discard(t)

    task.add_done_callback(_done)


async def shutdown_proxy_deferred_tasks() -> None:
    """取消并等待所有已登记的代理延迟任务（用于应用关闭与 ASGI 测试 fixture 收尾）。"""
    pending = [t for t in list(_proxy_deferred_tasks) if not t.done()]
    for t in pending:
        t.cancel()
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)


BudgetReservation = tuple[str, str | None, str, str | None]


@dataclass
class ProxyContext:
    """单次 OpenAI 兼容代理调用的上下文。

    Attributes:
        team_id: **计费工作区**（与日志 ``gateway_team_id``、``gateway_request_logs.team_id``
            一致），为一次调用归属的租户键。
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


class ProxyUseCase:
    def __init__(
        self,
        session: AsyncSession,
        *,
        budget_service: BudgetService | None = None,
    ) -> None:
        self._session = session
        self._budget = budget_service or BudgetService()

    # ---------------------------------------------------------------------
    # 校验
    # ---------------------------------------------------------------------

    def _check_model(self, model: str, ctx: ProxyContext) -> None:
        allowed_models = ctx.allowed_models or (ctx.vkey.allowed_models if ctx.vkey else ())
        if allowed_models and model not in allowed_models:
            raise ModelNotAllowedError(model)

    def _check_capability(self, ctx: ProxyContext) -> None:
        allowed_capabilities = ctx.allowed_capabilities or (
            ctx.vkey.allowed_capabilities if ctx.vkey else ()
        )
        if allowed_capabilities and ctx.capability not in allowed_capabilities:
            raise CapabilityNotAllowedError(ctx.capability.value)

    async def _check_limits(self, ctx: ProxyContext, estimate_tokens: int = 0) -> None:
        """vkey + team 维度限流"""
        if ctx.rpm_limit is not None or ctx.tpm_limit is not None:
            rate_scope = "vkey" if ctx.vkey is not None else "platform_api_key_grant"
            rate_scope_id = (
                str(ctx.vkey.vkey_id)
                if ctx.vkey is not None
                else str(ctx.platform_api_key_grant_id or ctx.platform_api_key_id)
                if (ctx.platform_api_key_grant_id or ctx.platform_api_key_id)
                else None
            )
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

    async def _check_budget(self, ctx: ProxyContext) -> list[BudgetReservation]:
        """检查 team/user/key 维度预算（含全模型汇总行与可选模型行）。"""
        repo = BudgetRepository(self._session)
        scopes_to_check: list[tuple[str, uuid.UUID | None]] = [
            ("team", ctx.team_id),
        ]
        if ctx.user_id:
            scopes_to_check.append(("user", ctx.user_id))
        if ctx.vkey:
            scopes_to_check.append(("key", ctx.vkey.vkey_id))

        reservations: list[BudgetReservation] = []
        periods = (PERIOD_DAILY, PERIOD_MONTHLY, PERIOD_TOTAL)
        for scope, scope_id in scopes_to_check:
            for period in periods:
                rows: list[GatewayBudget] = []
                agg = await repo.get_for(scope, scope_id, period, model_name=None)
                if agg is not None:
                    rows.append(agg)
                if ctx.budget_model:
                    spec = await repo.get_for(scope, scope_id, period, model_name=ctx.budget_model)
                    if spec is not None:
                        rows.append(spec)
                for budget in rows:
                    check = await self._budget.check_budget(
                        scope=scope,
                        scope_id=str(scope_id) if scope_id else None,
                        period=period,
                        limit_usd=budget.limit_usd,
                        limit_tokens=budget.limit_tokens,
                        limit_requests=budget.limit_requests,
                        budget_model_name=budget.model_name,
                    )
                    if not check.allowed:
                        await self._release_budget_reservations(reservations)
                        raise BudgetExceededError(
                            scope=scope,
                            period=period,
                            limit=float(
                                budget.limit_usd
                                or budget.limit_tokens
                                or budget.limit_requests
                                or 0
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
                        scope_id_str = str(scope_id) if scope_id else None
                        try:
                            await self._budget.reserve(
                                scope=scope,
                                scope_id=scope_id_str,
                                period=period,
                                limit_requests=budget.limit_requests,
                                budget_model_name=budget.model_name,
                            )
                        except Exception:
                            await self._release_budget_reservations(reservations)
                            raise
                        reservations.append((scope, scope_id_str, period, budget.model_name))
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
        """按虚拟模型名解析 GatewayModel → 凭据，供日志归因（与 Router deployment model_info 对齐）。"""
        if not virtual_model:
            return {}
        record = await GatewayModelRepository(self._session).get_by_name(team_id, virtual_model)
        if record is None:
            return {}
        cred = await ProviderCredentialRepository(self._session).get(record.credential_id)
        if cred is None:
            return {}
        return {
            "gateway_credential_id": str(cred.id),
            "gateway_credential_name_snapshot": cred.name,
            "gateway_credential_scope": cred.scope,
            "gateway_provider": record.provider,
        }

    async def _build_metadata(
        self,
        ctx: ProxyContext,
        *,
        user_kwargs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        team = await TeamRepository(self._session).get(ctx.team_id)
        verbose_log = bool(ctx.store_full_messages)
        meta: dict[str, Any] = {
            "gateway_team_id": str(ctx.team_id),
            "gateway_user_id": str(ctx.user_id) if ctx.user_id else None,
            "gateway_vkey_id": str(ctx.vkey.vkey_id) if ctx.vkey else None,
            "gateway_inbound_via": ctx.inbound_via,
            "gateway_platform_api_key_id": (
                str(ctx.platform_api_key_id) if ctx.platform_api_key_id else None
            ),
            "gateway_platform_api_key_grant_id": (
                str(ctx.platform_api_key_grant_id) if ctx.platform_api_key_grant_id else None
            ),
            "gateway_capability": ctx.capability.value,
            "gateway_request_id": ctx.request_id,
            "gateway_team_snapshot": ({"name": team.name, "kind": team.kind} if team else None),
            "gateway_vkey_name_snapshot": ctx.vkey.vkey_name if ctx.vkey else None,
            "guardrail_enabled": ctx.guardrail_enabled,
            "gateway_store_full_messages": verbose_log,
            "gateway_log_prompt_max_chars": int(settings.gateway_request_log_prompt_max_chars),
            "gateway_log_response_max_chars": int(
                settings.gateway_request_log_response_verbose_max_chars
                if verbose_log
                else settings.gateway_request_log_response_preview_max_chars
            ),
        }
        if user_kwargs:
            user_meta = user_kwargs.get("metadata") or {}
            if isinstance(user_meta, dict):
                meta.update(
                    {
                        k: v
                        for k, v in user_meta.items()
                        if k not in meta and not str(k).startswith("gateway_")
                    }
                )
            raw_model = user_kwargs.get("model")
            virtual_model = str(raw_model).strip() if raw_model is not None else None
            if virtual_model:
                meta.update(
                    await self._credential_metadata_for_virtual_model(ctx.team_id, virtual_model)
                )
                snap = await get_route_snapshot_metadata(self._session, ctx.team_id, virtual_model)
                if snap is not None:
                    meta["gateway_route_snapshot"] = snap
        return meta

    async def _should_use_internal_direct_litellm(self, ctx: ProxyContext, model: str) -> bool:
        """内部 system vkey 在没有注册 Gateway 模型/路由时可直连并继续落日志。"""
        if settings.gateway_proxy_disable_internal_direct_litellm:
            return False
        if ctx.vkey is None or not ctx.vkey.is_system:
            return False

        model_record = await GatewayModelRepository(self._session).get_by_name(ctx.team_id, model)
        if model_record is not None and model_record.enabled:
            return False

        route = await GatewayRouteRepository(self._session).get_by_virtual_model(ctx.team_id, model)
        return route is None

    @staticmethod
    def _is_router_model_miss(exc: Exception) -> bool:
        message = str(exc).lower()
        return any(
            marker in message
            for marker in (
                "no deployments available",
                "no deployment",
                "no models available",
                "unable to find deployment",
                "model not found",
                "could not find model",
            )
        )

    async def _direct_chat_completion(self, kwargs: dict[str, Any]) -> Any:
        from litellm import acompletion

        from domains.gateway.infrastructure.router_singleton import (
            ensure_gateway_callbacks,
        )

        ensure_gateway_callbacks()
        return await acompletion(**kwargs)

    async def _direct_embedding(self, kwargs: dict[str, Any]) -> Any:
        from litellm import aembedding

        from domains.gateway.infrastructure.router_singleton import (
            ensure_gateway_callbacks,
        )

        ensure_gateway_callbacks()
        return await aembedding(**kwargs)

    # ---------------------------------------------------------------------
    # 主入口
    # ---------------------------------------------------------------------

    async def chat_completion(
        self,
        ctx: ProxyContext,
        body: dict[str, Any],
    ) -> dict[str, Any] | AsyncIterator[dict[str, Any]]:
        """处理 /v1/chat/completions"""
        ctx.capability = GatewayCapability.CHAT
        model = str(body.get("model", "")).strip()
        if not model:
            raise ValueError("model is required")
        ctx.budget_model = model

        self._check_model(model, ctx)
        self._check_capability(ctx)
        # 估算 token：粗略按 messages 总长度 / 4
        estimate_tokens = sum(
            len(str(m.get("content", ""))) for m in (body.get("messages") or [])
        ) // 4 + int(body.get("max_tokens") or 0)
        await self._check_limits(ctx, estimate_tokens=estimate_tokens)
        reservations = await self._check_budget(ctx)

        metadata = await self._build_metadata(ctx, user_kwargs=body)
        kwargs = dict(body)
        kwargs["metadata"] = metadata

        stream = bool(body.get("stream"))
        try:
            if await self._should_use_internal_direct_litellm(ctx, model):
                response = await self._direct_chat_completion(kwargs)
            else:
                router = await get_router(self._session)
                response = await router.acompletion(**kwargs)
        except Exception as exc:
            if self._is_router_model_miss(exc) and await self._should_use_internal_direct_litellm(
                ctx, model
            ):
                try:
                    response = await self._direct_chat_completion(kwargs)
                except Exception:
                    await self._release_budget_reservations(reservations)
                    raise
            else:
                await self._release_budget_reservations(reservations)
                raise
        if stream:
            return _adapt_stream(response, ctx, self._budget)
        return _adapt_response(response, ctx, self._budget)

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

        metadata = await self._build_metadata(ctx, user_kwargs=body)
        kwargs = dict(body)
        kwargs["metadata"] = metadata
        try:
            if await self._should_use_internal_direct_litellm(ctx, model):
                response = await self._direct_embedding(kwargs)
            else:
                router = await get_router(self._session)
                response = await router.aembedding(**kwargs)
        except Exception:
            await self._release_budget_reservations(reservations)
            raise
        return _adapt_response(response, ctx, self._budget)

    async def image_generation(
        self,
        ctx: ProxyContext,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        ctx.capability = GatewayCapability.IMAGE
        ctx.budget_model = self._optional_body_model(body)
        self._check_capability(ctx)
        await self._check_limits(ctx)
        reservations = await self._check_budget(ctx)
        metadata = await self._build_metadata(ctx, user_kwargs=body)
        kwargs = dict(body)
        kwargs["metadata"] = metadata
        try:
            router = await get_router(self._session)
            response = await router.aimage_generation(**kwargs)
        except Exception:
            await self._release_budget_reservations(reservations)
            raise
        return _adapt_response(response, ctx, self._budget)

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
        metadata = await self._build_metadata(ctx, user_kwargs=body)
        kwargs = dict(body)
        kwargs["metadata"] = metadata
        try:
            router = await get_router(self._session)
            response = await router.atranscription(**kwargs)
        except Exception:
            await self._release_budget_reservations(reservations)
            raise
        return _adapt_response(response, ctx, self._budget)

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
        metadata = await self._build_metadata(ctx, user_kwargs=body)
        kwargs = dict(body)
        kwargs["metadata"] = metadata
        # 使用全局 litellm.aspeech 因为 Router 不一定暴露 aspeech
        from litellm import aspeech

        try:
            result = await aspeech(**kwargs)
        except Exception:
            await self._release_budget_reservations(reservations)
            raise
        # TTS 多为二进制返回，无 usage；仍结算请求/占位 token 与 DB 用量，与 limit_requests 预扣对齐
        _schedule_settle_usage(
            ctx,
            self._budget,
            tokens=0,
            cost=Decimal("0"),
            requests=1,
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
        metadata = await self._build_metadata(ctx, user_kwargs=body)
        kwargs = dict(body)
        kwargs["metadata"] = metadata
        from litellm import arerank

        try:
            response = await arerank(**kwargs)
        except Exception:
            await self._release_budget_reservations(reservations)
            raise
        return _adapt_response(response, ctx, self._budget)

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
        metadata = await self._build_metadata(ctx, user_kwargs=body)
        kwargs = dict(body)
        kwargs["metadata"] = metadata
        from litellm import amoderation

        try:
            response = await amoderation(**kwargs)
        except Exception:
            await self._release_budget_reservations(reservations)
            raise
        return _adapt_response(response, ctx, self._budget)

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
        await self._check_limits(ctx)
        reservations = await self._check_budget(ctx)
        metadata = await self._build_metadata(ctx, user_kwargs=body)
        kwargs = dict(body)
        kwargs["metadata"] = metadata
        from litellm import avideo_generation

        try:
            response = await avideo_generation(**kwargs)
        except Exception:
            await self._release_budget_reservations(reservations)
            raise
        return _adapt_response(response, ctx, self._budget)


# =============================================================================
# 响应适配 + 结算
# =============================================================================


def _to_dict(obj: Any) -> dict[str, Any]:
    if isinstance(obj, dict):
        return obj
    for attr in ("model_dump", "dict"):
        method = getattr(obj, attr, None)
        if callable(method):
            with suppress(Exception):
                return method()
    return {}


def _adapt_response(
    response: Any,
    ctx: ProxyContext,
    budget: BudgetService,
) -> dict[str, Any]:
    data = _to_dict(response)
    usage = data.get("usage") or {}
    tokens = int(usage.get("total_tokens", 0) or 0) if isinstance(usage, dict) else 0
    cost = _calc_cost(response)
    _schedule_settle_usage(ctx, budget, tokens=tokens, cost=cost, requests=1)
    return data


async def _adapt_stream(
    stream: Any,
    ctx: ProxyContext,
    budget: BudgetService,
) -> AsyncGenerator[dict[str, Any], None]:
    """转为 SSE 友好的 dict 流，并在末帧结算"""
    total_tokens = 0
    last_usage: dict[str, Any] | None = None
    async for chunk in stream:
        data = _to_dict(chunk)
        usage = data.get("usage")
        if isinstance(usage, dict):
            last_usage = usage
        yield data
    # 末帧结算
    if last_usage:
        total_tokens = int(last_usage.get("total_tokens", 0) or 0)
    cost = Decimal("0")  # 流式 cost 由 callbacks 落账
    await _settle_usage(ctx, budget, tokens=total_tokens, cost=cost, requests=1)


async def _settle_usage(
    ctx: ProxyContext,
    budget: BudgetService,
    *,
    tokens: int,
    cost: Decimal,
    requests: int,
) -> None:
    scope_items = (
        ("team", str(ctx.team_id)),
        ("user", str(ctx.user_id) if ctx.user_id else None),
        ("key", str(ctx.vkey.vkey_id) if ctx.vkey else None),
    )
    periods = (PERIOD_DAILY, PERIOD_MONTHLY, PERIOD_TOTAL)
    model_keys: list[str | None] = [None]
    if ctx.budget_model:
        model_keys.append(ctx.budget_model)

    for scope, scope_id in scope_items:
        if scope_id is None:
            continue
        for period in periods:
            for mk in model_keys:
                with suppress(Exception):
                    await budget.commit(
                        scope=scope,
                        scope_id=scope_id,
                        period=period,
                        delta_cost=cost,
                        delta_tokens=tokens,
                        budget_model_name=mk,
                    )

    with suppress(Exception):
        async with get_session_context() as session:
            repo = BudgetRepository(session)
            for scope, scope_id in scope_items:
                if scope_id is None:
                    continue
                scope_uuid = uuid.UUID(scope_id)
                for period in periods:
                    for mk in model_keys:
                        record = await repo.get_for(scope, scope_uuid, period, model_name=mk)
                        if record is None:
                            continue
                        await repo.settle_usage(
                            record.id,
                            delta_usd=cost,
                            delta_tokens=tokens,
                            delta_requests=requests,
                        )


def _schedule_settle_usage(
    ctx: ProxyContext,
    budget: BudgetService,
    *,
    tokens: int,
    cost: Decimal,
    requests: int,
) -> None:
    """异步结算（不 await 失败也不影响响应）；任务登记以便测试/进程退出时收口。"""

    async def _settle() -> None:
        await _settle_usage(ctx, budget, tokens=tokens, cost=cost, requests=requests)

    with suppress(RuntimeError):
        settle_task = asyncio.create_task(_settle())
        register_proxy_deferred_task(settle_task)


def _calc_cost(response: Any) -> Decimal:
    try:
        from litellm import completion_cost

        cost = completion_cost(completion_response=response)
        return Decimal(str(cost or 0))
    except Exception:  # pragma: no cover
        return Decimal("0")


__all__ = [
    "BudgetExceededError",
    "CapabilityNotAllowedError",
    "GuardrailBlockedError",
    "ModelNotAllowedError",
    "ProxyContext",
    "ProxyUseCase",
    "RateLimitExceededError",
]
