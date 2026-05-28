"""
ProxyUseCase - 网关调用编排门面（``/v1/*``）。

入站护栏 → ``ProxyGuard``；metadata → ``ProxyMetadataBuilder``；
LiteLLM → ``ProxyLiteLLMClient``；对话入口 → ``proxy_chat_entries``；
非对话入口 → ``proxy_non_chat_pipeline``。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from domains.gateway.application.budget_service import BudgetService
from domains.gateway.application.entitlement_guard import EntitlementGuard
from domains.gateway.application.prompt_cache_middleware import get_prompt_cache_middleware
from domains.gateway.application.proxy_chat_entries import ProxyChatMixin
from domains.gateway.application.proxy_context import EntitlementReservationState, ProxyContext
from domains.gateway.application.proxy_guard import ProxyGuard
from domains.gateway.application.proxy_litellm_client import ProxyLiteLLMClient
from domains.gateway.application.proxy_litellm_kwargs import (
    prepare_litellm_invoke as build_litellm_invoke,
)
from domains.gateway.application.proxy_metadata_builder import (
    PreparedLitellmKwargs,
    ProxyMetadataBuilder,
)
from domains.gateway.application.proxy_non_chat_pipeline import ProxyNonChatMixin
from domains.gateway.application.proxy_timing import ProxyPrepareTimings
from domains.gateway.application.quota_plan_service import get_quota_plan_service
from domains.gateway.application.upstream_adapter import UpstreamAdapter

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from domains.gateway.application.model_or_route_resolution import ResolvedModelName


class ProxyUseCase(ProxyChatMixin, ProxyNonChatMixin):
    """对外 LLM 代理用例（编排门面，不含 ``_`` 前缀委托方法）。

    **公开入口**：``chat_completion`` / ``anthropic_messages`` / ``embedding`` /
    ``image_generation`` / ``audio_*`` / ``rerank`` / ``moderation`` /
    ``video_generation``（定义于 ``proxy_chat_entries`` / ``proxy_non_chat_pipeline``）。

    **协作模块**：领域规则 ``domain.proxy_policy``；metadata ``ProxyMetadataBuilder``；
    LiteLLM ``ProxyLiteLLMClient``；响应/结算 ``proxy_response_adapter``。
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
    def session(self) -> AsyncSession:
        return self._session

    @property
    def guard(self) -> ProxyGuard:
        return self._guard

    @property
    def budget_service(self) -> BudgetService:
        return self._budget

    @property
    def entitlement_guard(self) -> EntitlementGuard:
        return self._entitlement_guard

    @property
    def metadata_builder(self) -> ProxyMetadataBuilder:
        return self._metadata_builder

    @property
    def litellm(self) -> ProxyLiteLLMClient:
        return self._litellm

    async def prepare_litellm_invoke(
        self,
        ctx: ProxyContext,
        body: dict[str, Any],
        *,
        resolved: ResolvedModelName | None = None,
        timings: ProxyPrepareTimings | None = None,
    ) -> tuple[PreparedLitellmKwargs, dict[str, Any]]:
        """返回 ``PreparedLitellmKwargs`` 与最终 kwargs（供 embedding 等读取 ``resolved``）。"""
        return await build_litellm_invoke(
            self._metadata_builder,
            ctx,
            body,
            upstream_adapter=self._upstream_adapter,
            prompt_cache=self._prompt_cache,
            resolved=resolved,
            timings=timings,
        )

    async def prepare_litellm_kwargs(
        self,
        ctx: ProxyContext,
        body: dict[str, Any],
        *,
        resolved: ResolvedModelName | None = None,
    ) -> dict[str, Any]:
        """拼装经 upstream 适配与 prompt cache 处理后的 LiteLLM kwargs。"""
        _prepared, kwargs = await self.prepare_litellm_invoke(ctx, body, resolved=resolved)
        return kwargs


__all__ = [
    "EntitlementReservationState",
    "ProxyContext",
    "ProxyUseCase",
]
