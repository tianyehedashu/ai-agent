"""代理入站护栏：模型/能力校验、限流、预算预扣、entitlement。

把原本散落在 ``ProxyUseCase`` 内部 ``_check_*`` / ``_release_*`` 私有方法的逻辑
抽到独立服务，让 ``ProxyUseCase`` 与 ``proxy_chat_pipeline`` 都依赖**同一份公开 API**，
彻底消除「跨模块访问 `_` 前缀方法」（§3 红线）。

调用顺序契约（由消费方编排，本类不强制）：

1. :meth:`check_model` + :meth:`check_capability`
2. :meth:`assert_request_capability_matches_model`（按需）
3. :meth:`check_limits`
4. :meth:`check_budget` → 持有 ``reservations``
5. :meth:`check_entitlement`（失败时调 :meth:`release_budget_reservations`）
6. 出站调用前 / 失败时：:meth:`release_budget_reservations` +
   :meth:`release_entitlement_reservations` 释放预扣
"""

from __future__ import annotations

from contextlib import suppress
from typing import TYPE_CHECKING

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
from domains.gateway.domain.errors import BudgetExceededError
from domains.gateway.domain.proxy_policy import (
    assert_capability_allowed,
    assert_model_allowed,
    assert_registered_model_capability,
    budget_scope_targets,
    build_budget_check_plan,
    first_present_limit,
    rate_limit_target,
)
from domains.gateway.infrastructure.repositories.budget_repository import BudgetRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from domains.gateway.application.proxy_use_case import ProxyContext


BudgetReservation = tuple[str, str | None, str, str | None]


class ProxyGuard:
    """代理入站护栏服务。"""

    def __init__(
        self,
        session: AsyncSession,
        budget_service: BudgetService,
        entitlement_guard: EntitlementGuard,
    ) -> None:
        self._session = session
        self._budget = budget_service
        self._entitlement_guard = entitlement_guard

    # ---------------------------------------------------------------------
    # 模型与能力校验
    # ---------------------------------------------------------------------

    def check_model(self, model: str, ctx: ProxyContext) -> None:
        allowed_models = ctx.allowed_models or (ctx.vkey.allowed_models if ctx.vkey else ())
        assert_model_allowed(model, allowed_models)

    def check_capability(self, ctx: ProxyContext) -> None:
        allowed_capabilities = ctx.allowed_capabilities or (
            ctx.vkey.allowed_capabilities if ctx.vkey else ()
        )
        assert_capability_allowed(ctx.capability, allowed_capabilities)

    async def assert_request_capability_matches_model(
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

    # ---------------------------------------------------------------------
    # 限流
    # ---------------------------------------------------------------------

    async def check_limits(self, ctx: ProxyContext, *, estimate_tokens: int = 0) -> None:
        """vkey + team 维度限流；按 ctx 显式 rpm/tpm > vkey 默认 rpm/tpm 顺序。"""
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

    # ---------------------------------------------------------------------
    # 预算预扣 / 释放
    # ---------------------------------------------------------------------

    async def check_budget(self, ctx: ProxyContext) -> list[BudgetReservation]:
        """按 ``BudgetCheckPlan`` 顺序扫描 team/user/key 维度预算。

        预算扫描坐标的纯逻辑（哪些 scope×period×model_key 该查）由
        ``domains.gateway.domain.proxy_policy.build_budget_check_plan`` 决定，
        本方法只负责按计划查仓储、调用 ``BudgetService``、抛错与累积请求级预扣。
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
                await self.release_budget_reservations(reservations)
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
                    await self.release_budget_reservations(reservations)
                    raise
                reservations.append((query.scope, scope_id_str, query.period, budget.model_name))
        return reservations

    async def release_budget_reservations(
        self, reservations: list[BudgetReservation]
    ) -> None:
        for scope, scope_id, period, budget_model_name in reservations:
            with suppress(Exception):
                await self._budget.release(
                    scope=scope,
                    scope_id=scope_id,
                    period=period,
                    budget_model_name=budget_model_name,
                )

    # ---------------------------------------------------------------------
    # Entitlement 预扣 / 释放
    # ---------------------------------------------------------------------

    async def check_entitlement(
        self, ctx: ProxyContext, model: str | None, *, estimate_tokens: int = 0
    ) -> None:
        """根据 ctx (vkey_id 或 apikey_grant_id) 解析活跃 entitlement plan 并预扣。

        无匹配 plan = 默认放行；命中但任一桶耗尽抛 ``EntitlementPlanExhaustedError``。
        """
        from domains.gateway.application.proxy_use_case import EntitlementReservationState

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

    async def release_entitlement_reservations(self, ctx: ProxyContext) -> None:
        state = ctx.entitlement_state
        if state is None or not state.reservations:
            return
        with suppress(Exception):
            await self._entitlement_guard.release(state.plan_id, state.reservations)
        ctx.entitlement_state = None


__all__ = ["BudgetReservation", "ProxyGuard"]
