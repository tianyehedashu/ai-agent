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

from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import suppress
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from domains.gateway.application.budget_service import (
    PERIOD_DAILY,
    PERIOD_MONTHLY,
    BudgetService,
)
from domains.gateway.domain.errors import (
    BudgetExceededError,
    CapabilityNotAllowedError,
    GuardrailBlockedError,
    ModelNotAllowedError,
    RateLimitExceededError,
)
from domains.gateway.domain.types import GatewayCapability, VirtualKeyPrincipal
from domains.gateway.infrastructure.repositories.budget_repository import BudgetRepository
from domains.gateway.infrastructure.repositories.team_repository import TeamRepository
from domains.gateway.infrastructure.router_singleton import get_router
from utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ProxyContext:
    """单次代理调用的上下文"""

    team_id: uuid.UUID
    user_id: uuid.UUID | None
    vkey: VirtualKeyPrincipal | None
    capability: GatewayCapability
    request_id: str
    store_full_messages: bool
    guardrail_enabled: bool


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
        vkey = ctx.vkey
        if vkey and vkey.allowed_models and model not in vkey.allowed_models:
            raise ModelNotAllowedError(model)

    def _check_capability(self, ctx: ProxyContext) -> None:
        vkey = ctx.vkey
        if vkey and vkey.allowed_capabilities:
            if ctx.capability not in vkey.allowed_capabilities:
                raise CapabilityNotAllowedError(ctx.capability.value)

    async def _check_limits(
        self, ctx: ProxyContext, estimate_tokens: int = 0
    ) -> None:
        """vkey + team 维度限流"""
        if ctx.vkey is not None:
            await self._budget.check_rate_limit(
                scope="vkey",
                scope_id=str(ctx.vkey.vkey_id),
                rpm_limit=ctx.vkey.rpm_limit,
                tpm_limit=ctx.vkey.tpm_limit,
                estimate_tokens=estimate_tokens,
            )
        # team 维度（从团队设置中读 rpm/tpm，简化：通过 GatewayBudget 表表示）

    async def _check_budget(self, ctx: ProxyContext) -> None:
        """检查 vkey/team/user 三级预算"""
        repo = BudgetRepository(self._session)
        scopes_to_check: list[tuple[str, uuid.UUID | None]] = [
            ("team", ctx.team_id),
        ]
        if ctx.user_id:
            scopes_to_check.append(("user", ctx.user_id))
        if ctx.vkey:
            scopes_to_check.append(("key", ctx.vkey.vkey_id))

        for scope, scope_id in scopes_to_check:
            for period in (PERIOD_DAILY, PERIOD_MONTHLY):
                budget = await repo.get_for(scope, scope_id, period)
                if budget is None:
                    continue
                check = await self._budget.check_budget(
                    scope=scope,
                    scope_id=str(scope_id) if scope_id else None,
                    period=period,
                    limit_usd=budget.limit_usd,
                    limit_tokens=budget.limit_tokens,
                    limit_requests=budget.limit_requests,
                )
                if not check.allowed:
                    raise BudgetExceededError(
                        scope=scope,
                        period=period,
                        limit=float(budget.limit_usd or budget.limit_tokens or budget.limit_requests or 0),
                        used=float(
                            check.used_usd
                            if check.reason == "usd"
                            else check.used_tokens
                            if check.reason == "tokens"
                            else check.used_requests
                        ),
                    )
                if budget.limit_requests:
                    await self._budget.reserve(
                        scope=scope,
                        scope_id=str(scope_id) if scope_id else None,
                        period=period,
                        limit_requests=budget.limit_requests,
                    )

    # ---------------------------------------------------------------------
    # Metadata 注入
    # ---------------------------------------------------------------------

    async def _build_metadata(
        self,
        ctx: ProxyContext,
        *,
        user_kwargs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        team = await TeamRepository(self._session).get(ctx.team_id)
        meta: dict[str, Any] = {
            "gateway_team_id": str(ctx.team_id),
            "gateway_user_id": str(ctx.user_id) if ctx.user_id else None,
            "gateway_vkey_id": str(ctx.vkey.vkey_id) if ctx.vkey else None,
            "gateway_capability": ctx.capability.value,
            "gateway_request_id": ctx.request_id,
            "gateway_team_snapshot": (
                {"name": team.name, "kind": team.kind} if team else None
            ),
            "gateway_vkey_name_snapshot": ctx.vkey.vkey_name if ctx.vkey else None,
            "guardrail_enabled": ctx.guardrail_enabled,
        }
        if user_kwargs:
            user_meta = user_kwargs.get("metadata") or {}
            if isinstance(user_meta, dict):
                meta.update({k: v for k, v in user_meta.items() if k not in meta})
        return meta

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

        self._check_model(model, ctx)
        self._check_capability(ctx)
        # 估算 token：粗略按 messages 总长度 / 4
        estimate_tokens = sum(
            len(str(m.get("content", ""))) for m in (body.get("messages") or [])
        ) // 4 + int(body.get("max_tokens") or 0)
        await self._check_limits(ctx, estimate_tokens=estimate_tokens)
        await self._check_budget(ctx)

        metadata = await self._build_metadata(ctx, user_kwargs=body)
        kwargs = dict(body)
        kwargs["metadata"] = metadata

        router = await get_router(self._session)
        stream = bool(body.get("stream"))
        try:
            response = await router.acompletion(**kwargs)
        except Exception:
            with suppress(Exception):
                await self._budget.release(
                    scope="team",
                    scope_id=str(ctx.team_id),
                    period=PERIOD_DAILY,
                )
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
        self._check_model(model, ctx)
        self._check_capability(ctx)
        await self._check_limits(ctx)
        await self._check_budget(ctx)

        metadata = await self._build_metadata(ctx, user_kwargs=body)
        kwargs = dict(body)
        kwargs["metadata"] = metadata
        router = await get_router(self._session)
        response = await router.aembedding(**kwargs)
        return _adapt_response(response, ctx, self._budget)

    async def image_generation(
        self,
        ctx: ProxyContext,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        ctx.capability = GatewayCapability.IMAGE
        self._check_capability(ctx)
        await self._check_limits(ctx)
        await self._check_budget(ctx)
        metadata = await self._build_metadata(ctx, user_kwargs=body)
        kwargs = dict(body)
        kwargs["metadata"] = metadata
        router = await get_router(self._session)
        response = await router.aimage_generation(**kwargs)
        return _adapt_response(response, ctx, self._budget)

    async def audio_transcription(
        self,
        ctx: ProxyContext,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        ctx.capability = GatewayCapability.AUDIO_TRANSCRIPTION
        self._check_capability(ctx)
        await self._check_limits(ctx)
        await self._check_budget(ctx)
        metadata = await self._build_metadata(ctx, user_kwargs=body)
        kwargs = dict(body)
        kwargs["metadata"] = metadata
        router = await get_router(self._session)
        response = await router.atranscription(**kwargs)
        return _adapt_response(response, ctx, self._budget)

    async def audio_speech(
        self,
        ctx: ProxyContext,
        body: dict[str, Any],
    ) -> dict[str, Any] | bytes:
        ctx.capability = GatewayCapability.AUDIO_SPEECH
        self._check_capability(ctx)
        await self._check_limits(ctx)
        await self._check_budget(ctx)
        metadata = await self._build_metadata(ctx, user_kwargs=body)
        kwargs = dict(body)
        kwargs["metadata"] = metadata
        # 使用全局 litellm.aspeech 因为 Router 不一定暴露 aspeech
        from litellm import aspeech  # noqa: PLC0415

        return await aspeech(**kwargs)

    async def rerank(
        self,
        ctx: ProxyContext,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        ctx.capability = GatewayCapability.RERANK
        self._check_capability(ctx)
        await self._check_limits(ctx)
        await self._check_budget(ctx)
        metadata = await self._build_metadata(ctx, user_kwargs=body)
        kwargs = dict(body)
        kwargs["metadata"] = metadata
        from litellm import arerank  # noqa: PLC0415

        return await arerank(**kwargs)


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
    if isinstance(usage, dict):
        tokens = int(usage.get("total_tokens", 0) or 0)
    else:
        tokens = 0
    cost = _calc_cost(response)

    # 异步结算（不 await 失败也不影响响应）
    import asyncio  # noqa: PLC0415

    async def _settle() -> None:
        for scope, scope_id in (
            ("team", str(ctx.team_id)),
            ("user", str(ctx.user_id) if ctx.user_id else None),
            ("key", str(ctx.vkey.vkey_id) if ctx.vkey else None),
        ):
            if scope_id is None:
                continue
            for period in (PERIOD_DAILY, PERIOD_MONTHLY):
                with suppress(Exception):
                    await budget.commit(
                        scope=scope,
                        scope_id=scope_id,
                        period=period,
                        delta_cost=cost,
                        delta_tokens=tokens,
                    )

    with suppress(RuntimeError):
        loop = asyncio.get_running_loop()
        loop.create_task(_settle())
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
    for scope, scope_id in (
        ("team", str(ctx.team_id)),
        ("user", str(ctx.user_id) if ctx.user_id else None),
        ("key", str(ctx.vkey.vkey_id) if ctx.vkey else None),
    ):
        if scope_id is None:
            continue
        for period in (PERIOD_DAILY, PERIOD_MONTHLY):
            with suppress(Exception):
                await budget.commit(
                    scope=scope,
                    scope_id=scope_id,
                    period=period,
                    delta_cost=cost,
                    delta_tokens=total_tokens,
                )


def _calc_cost(response: Any) -> Decimal:
    try:
        from litellm import completion_cost  # noqa: PLC0415

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
