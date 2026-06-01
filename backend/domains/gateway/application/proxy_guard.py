"""代理入站护栏：模型/能力校验、限流、预算预扣、entitlement。

把原本散落在 ``ProxyUseCase`` 内部 ``_check_*`` / ``_release_*`` 私有方法的逻辑
抽到独立服务，让 ``ProxyUseCase`` 与 ``proxy_chat_pipeline`` 都依赖**同一份公开 API**，
彻底消除「跨模块访问 `_` 前缀方法」（§3 红线）。

调用顺序契约（由消费方编排，本类不强制）：

1. :meth:`check_model`
2. :meth:`resolve_and_validate_request_model`（按需；preflight 单次 resolve）
3. :meth:`check_capability`
4. :meth:`check_limits`
5. :meth:`check_budget` → 持有 ``reservations``
6. :meth:`check_entitlement`（失败时调 :meth:`release_budget_reservations`）
7. 出站调用前 / 失败时：:meth:`release_budget_reservations` +
   :meth:`release_entitlement_reservations` 释放预扣
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from typing import TYPE_CHECKING
import uuid

from bootstrap.config import settings
from domains.gateway.application.budget_config_cache import (
    BudgetConfigRow,
    get_cached_budget_by_plan,
)
from domains.gateway.application.budget_service import (
    PERIOD_DAILY,
    PERIOD_MONTHLY,
    PERIOD_TOTAL,
    BudgetService,
    BudgetUsageCoord,
    redis_model_segment_for_budget,
    redis_tenant_segment_for_budget,
)
from domains.gateway.application.entitlement_guard import (
    EntitlementContext,
    EntitlementGuard,
)
from domains.gateway.application.model_or_route_resolution import (
    ResolvedModelName,
    resolve_model_or_route,
)
from domains.gateway.domain.errors import BudgetExceededError, GatewayModelNotFoundError
from domains.gateway.domain.policies.budget_exemption_policy import (
    should_skip_platform_budget_preflight,
)
from domains.gateway.domain.proxy_policy import (
    BudgetCheckQuery,
    BudgetReservation,
    allows_unregistered_gateway_model,
    assert_capability_allowed,
    assert_model_allowed,
    assert_registered_model_capability,
    build_budget_check_plan,
    first_present_limit,
    proxy_budget_targets,
    rate_limit_target,
)
from domains.gateway.infrastructure.repositories.budget_repository import BudgetRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from domains.gateway.application.proxy_context import ProxyContext
    from domains.gateway.infrastructure.models.budget import GatewayBudget


def _default_budget_repository_factory(session: AsyncSession) -> BudgetRepository:
    return BudgetRepository(session)


class ProxyGuard:
    """代理入站护栏服务。"""

    def __init__(
        self,
        session: AsyncSession,
        budget_service: BudgetService,
        entitlement_guard: EntitlementGuard,
        *,
        budget_repository_factory: Callable[[AsyncSession], BudgetRepository] | None = None,
    ) -> None:
        self._session = session
        self._budget = budget_service
        self._entitlement_guard = entitlement_guard
        self._budget_repo_factory = budget_repository_factory or _default_budget_repository_factory

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

    @staticmethod
    def _allows_unregistered_gateway_model(ctx: ProxyContext) -> bool:
        return allows_unregistered_gateway_model(
            vkey_is_system=ctx.vkey.is_system if ctx.vkey is not None else None,
            disable_internal_direct_litellm=settings.gateway_proxy_disable_internal_direct_litellm,
        )

    async def _team_label_for_proxy(
        self,
        team_id: uuid.UUID,
        viewer_user_id: uuid.UUID | None,
    ) -> str:
        from domains.identity.application.user_display import resolve_user_display_snapshot
        from domains.tenancy.application.team_service import TeamService
        from domains.tenancy.domain.team_display_label import format_team_display_label

        team = await TeamService(self._session).get_team(team_id)
        if team is None:
            return str(team_id)[:8]
        owner_hint: str | None = None
        if team.kind == "personal" and (
            viewer_user_id is None or viewer_user_id != team.owner_user_id
        ):
            owner_hint = await resolve_user_display_snapshot(self._session, team.owner_user_id)
        return format_team_display_label(
            kind=team.kind,
            name=team.name,
            owner_user_id=team.owner_user_id,
            viewer_user_id=viewer_user_id,
            owner_hint=owner_hint,
        )

    async def resolve_and_validate_request_model(
        self,
        ctx: ProxyContext,
        model: str,
        *,
        match_registered_capability: bool = True,
    ) -> ResolvedModelName | None:
        """单次 resolve；校验注册与 capability（system vkey 内部桥接除外）。"""
        name = model.strip()
        if not name:
            return None
        resolved = await resolve_model_or_route(
            self._session, ctx.team_id, name, user_id=ctx.user_id
        )
        if not self._allows_unregistered_gateway_model(ctx) and resolved is None:
            team_label = await self._team_label_for_proxy(ctx.team_id, ctx.user_id)
            raise GatewayModelNotFoundError(name, team_label=team_label)
        if match_registered_capability and resolved is not None:
            assert_registered_model_capability(
                model_name=name,
                requested=ctx.capability,
                registered_capability=str(resolved.record.capability),
                via_route=resolved.route is not None,
            )
        return resolved

    async def assert_gateway_model_registered(
        self,
        ctx: ProxyContext,
        model: str,
    ) -> None:
        """客户端 model 须在 Gateway 注册；未注册时不应把裸 model 交给 LiteLLM Router。"""
        await self.resolve_and_validate_request_model(ctx, model, match_registered_capability=False)

    async def assert_request_capability_matches_model(
        self,
        ctx: ProxyContext,
        model: str,
    ) -> None:
        """注册别名或路由主选 ``GatewayModel.capability`` 须与当前 HTTP 入口一致。"""
        name = model.strip()
        if not name:
            return
        resolved = await resolve_model_or_route(
            self._session, ctx.team_id, name, user_id=ctx.user_id
        )
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
        """vkey 或 platform API Key grant 维度 RPM/TPM 限流。

        按 ctx 显式 ``rpm_limit`` / ``tpm_limit`` 优先于 vkey 默认配置。
        """
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
                target_kind=rate_scope,
                target_id=rate_scope_id,
                rpm_limit=ctx.rpm_limit,
                tpm_limit=ctx.tpm_limit,
                estimate_tokens=estimate_tokens,
            )
        elif ctx.vkey is not None:
            await self._budget.check_rate_limit(
                target_kind="vkey",
                target_id=str(ctx.vkey.vkey_id),
                rpm_limit=ctx.vkey.rpm_limit,
                tpm_limit=ctx.vkey.tpm_limit,
                estimate_tokens=estimate_tokens,
            )

    # ---------------------------------------------------------------------
    # 预算预扣 / 释放
    # ---------------------------------------------------------------------

    async def is_platform_budget_exempt(
        self, ctx: ProxyContext, resolved: ResolvedModelName | None
    ) -> bool:
        """命中个人工作区模型时豁免全部平台配额（含成员总量 / 成员+凭据+模型）。

        仅当解析行的 ``tenant_id`` 等于计费团队（需判断该团队是否个人工作区）时才查询个人团队，
        系统模型 / 跨团队个人别名均无需查库。
        """
        if resolved is None or ctx.user_id is None:
            return False
        record_tenant_id = getattr(resolved.record, "tenant_id", None)
        if not isinstance(record_tenant_id, uuid.UUID):
            return False
        if record_tenant_id == ctx.team_id and ctx.personal_team_id is None:
            from domains.tenancy.application.team_service import TeamService

            personal = await TeamService(self._session).ensure_personal_team(ctx.user_id)
            ctx.personal_team_id = personal.id
        return should_skip_platform_budget_preflight(
            record_tenant_id,
            billing_team_id=ctx.team_id,
            personal_team_id=ctx.personal_team_id,
        )

    async def check_budget(
        self, ctx: ProxyContext, *, estimate_tokens: int = 0
    ) -> list[BudgetReservation]:
        """按 ``BudgetCheckPlan`` 顺序扫描 system/tenant/user/key 维度预算。"""
        repo = self._budget_repo_factory(self._session)
        targets = proxy_budget_targets(
            tenant_id=ctx.team_id,
            user_id=ctx.user_id,
            vkey_id=ctx.vkey.vkey_id if ctx.vkey else None,
        )
        plan = build_budget_check_plan(
            targets=targets,
            periods=(PERIOD_DAILY, PERIOD_MONTHLY, PERIOD_TOTAL),
            request_model=ctx.budget_model,
            tenant_id=ctx.team_id,
        )

        async def load_budget_rows() -> dict[
            tuple[
                str, uuid.UUID | None, str, str | None, uuid.UUID | None, uuid.UUID | None
            ],
            GatewayBudget,
        ]:
            return await repo.get_many_by_plan(plan)

        budget_by_coord = await get_cached_budget_by_plan(plan, load_budget_rows)

        check_items: list[
            tuple[BudgetCheckQuery, BudgetConfigRow, BudgetUsageCoord, str]
        ] = []
        for query in plan:
            budget = budget_by_coord.get(
                (
                    query.target_kind,
                    query.target_id,
                    query.period,
                    query.model_name,
                    query.credential_id,
                    query.tenant_id,
                )
            )
            if budget is None:
                continue
            target_id_str = str(query.target_id) if query.target_id is not None else None
            usage_coord = BudgetUsageCoord(
                target_kind=query.target_kind,
                target_id=target_id_str,
                period=query.period,
                model_segment=redis_model_segment_for_budget(budget.model_name),
                tenant_segment=redis_tenant_segment_for_budget(query.tenant_id),
            )
            check_items.append((query, budget, usage_coord, target_id_str))

        usage_coords = [item[2] for item in check_items]
        usage_by_coord = await self._budget.read_budget_usage_batch(usage_coords)

        reservations: list[BudgetReservation] = []
        for query, budget, usage_coord, target_id_str in check_items:
            prefetched = usage_by_coord.get(usage_coord)
            check = await self._budget.check_budget(
                target_kind=query.target_kind,
                target_id=target_id_str,
                period=query.period,
                limit_usd=budget.limit_usd,
                limit_tokens=budget.limit_tokens,
                limit_requests=budget.limit_requests,
                budget_model_name=budget.model_name,
                tenant_id=query.tenant_id,
                prefetched_usage=prefetched,
            )
            if not check.allowed:
                await self.release_budget_reservations(reservations)
                raise BudgetExceededError(
                    scope=query.target_kind,
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
            # 无 token/request 限额时跳过 reserve，减少 Redis 写入
            if (budget.limit_requests is None or budget.limit_requests <= 0) and (
                budget.limit_tokens is None or budget.limit_tokens <= 0 or estimate_tokens <= 0
            ):
                continue
            try:
                reserved_requests, reserved_tokens = await self._budget.reserve(
                    target_kind=query.target_kind,
                    target_id=target_id_str,
                    period=query.period,
                    limit_requests=budget.limit_requests,
                    limit_tokens=budget.limit_tokens,
                    estimate_tokens=estimate_tokens,
                    budget_model_name=budget.model_name,
                    tenant_id=query.tenant_id,
                )
            except Exception:
                await self.release_budget_reservations(reservations)
                raise
            if reserved_requests or reserved_tokens:
                reservations.append(
                    BudgetReservation(
                        target_kind=query.target_kind,
                        target_id=target_id_str,
                        period=query.period,
                        budget_model_name=budget.model_name,
                        reserved_requests=reserved_requests,
                        reserved_tokens=reserved_tokens,
                        tenant_id=query.tenant_id,
                    )
                )
        return reservations

    async def release_budget_reservations(self, reservations: list[BudgetReservation]) -> None:
        for reservation in reservations:
            with suppress(Exception):
                await self._budget.release(
                    target_kind=reservation.target_kind,
                    target_id=reservation.target_id,
                    period=reservation.period,
                    budget_model_name=reservation.budget_model_name,
                    reserved_requests=reservation.reserved_requests,
                    reserved_tokens=reservation.reserved_tokens,
                    tenant_id=reservation.tenant_id,
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
        from domains.gateway.application.proxy_context import EntitlementReservationState

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


__all__ = ["ProxyGuard"]
