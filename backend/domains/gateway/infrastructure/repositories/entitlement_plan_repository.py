"""EntitlementPlanRepository - 下游套餐仓储

加载 (vkey | apikey_grant) 范围内的活跃套餐 + 多层 quotas，供
EntitlementGuard 在 ProxyUseCase 入口路径上做配额预扣使用。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import and_, select

from domains.gateway.infrastructure.models.entitlement_plan import (
    EntitlementPlan,
    EntitlementPlanQuota,
)

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


ENTITLEMENT_SCOPE_VKEY = "vkey"
ENTITLEMENT_SCOPE_APIKEY_GRANT = "apikey_grant"


class EntitlementPlanRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, plan_id: uuid.UUID) -> EntitlementPlan | None:
        return await self._session.get(EntitlementPlan, plan_id)

    async def list_for_scope(self, scope: str, scope_id: uuid.UUID) -> list[EntitlementPlan]:
        stmt = (
            select(EntitlementPlan)
            .where(
                EntitlementPlan.target_kind == scope,
                EntitlementPlan.target_id == scope_id,
            )
            .order_by(EntitlementPlan.valid_from.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_active_for_scope(
        self,
        scope: str,
        scope_id: uuid.UUID,
        *,
        virtual_model: str | None = None,
        capability: str | None = None,
        now: datetime | None = None,
    ) -> EntitlementPlan | None:
        """返回当前活跃且匹配 model/capability 白名单的套餐；多条取 valid_from 最新。"""
        when = now or datetime.now(UTC)
        clauses = [
            EntitlementPlan.target_kind == scope,
            EntitlementPlan.target_id == scope_id,
            EntitlementPlan.is_active.is_(True),
            EntitlementPlan.valid_from <= when,
            EntitlementPlan.valid_until > when,
        ]
        stmt = (
            select(EntitlementPlan)
            .where(and_(*clauses))
            .order_by(EntitlementPlan.valid_from.desc())
        )
        rows = list((await self._session.execute(stmt)).scalars().all())
        for row in rows:
            included = list(row.included_models or [])
            if included and virtual_model is not None and virtual_model not in included:
                continue
            inc_caps = list(row.included_capabilities or [])
            if inc_caps and capability is not None and capability not in inc_caps:
                continue
            return row
        return None

    async def list_quotas(self, plan_id: uuid.UUID) -> list[EntitlementPlanQuota]:
        stmt = (
            select(EntitlementPlanQuota)
            .where(EntitlementPlanQuota.plan_id == plan_id)
            .order_by(EntitlementPlanQuota.window_seconds.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_with_quotas_for_scope(
        self, scope: str, scope_id: uuid.UUID
    ) -> list[tuple[EntitlementPlan, list[EntitlementPlanQuota]]]:
        plans = await self.list_for_scope(scope, scope_id)
        if not plans:
            return []
        plan_ids = [p.id for p in plans]
        qstmt = (
            select(EntitlementPlanQuota)
            .where(EntitlementPlanQuota.plan_id.in_(plan_ids))
            .order_by(EntitlementPlanQuota.window_seconds.asc())
        )
        rows = list((await self._session.execute(qstmt)).scalars().all())
        groups: dict[uuid.UUID, list[EntitlementPlanQuota]] = {p.id: [] for p in plans}
        for q in rows:
            groups[q.plan_id].append(q)
        return [(p, groups[p.id]) for p in plans]

    async def list_with_quotas_for_vkeys(
        self, vkey_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, list[tuple[EntitlementPlan, list[EntitlementPlanQuota]]]]:
        """批量拉取多个 vkey 的下游 plan + quotas（消除 N+1）。"""
        if not vkey_ids:
            return {}
        unique_ids = list(dict.fromkeys(vkey_ids))
        stmt = (
            select(EntitlementPlan)
            .where(
                EntitlementPlan.target_kind == ENTITLEMENT_SCOPE_VKEY,
                EntitlementPlan.target_id.in_(unique_ids),
            )
            .order_by(EntitlementPlan.valid_from.desc())
        )
        plans = list((await self._session.execute(stmt)).scalars().all())
        if not plans:
            return {vid: [] for vid in unique_ids}
        plan_ids = [p.id for p in plans]
        qstmt = (
            select(EntitlementPlanQuota)
            .where(EntitlementPlanQuota.plan_id.in_(plan_ids))
            .order_by(EntitlementPlanQuota.window_seconds.asc())
        )
        quota_rows = list((await self._session.execute(qstmt)).scalars().all())
        quota_groups: dict[uuid.UUID, list[EntitlementPlanQuota]] = {p.id: [] for p in plans}
        for q in quota_rows:
            quota_groups[q.plan_id].append(q)
        out: dict[uuid.UUID, list[tuple[EntitlementPlan, list[EntitlementPlanQuota]]]] = {
            vid: [] for vid in unique_ids
        }
        for plan in plans:
            out[plan.target_id].append((plan, quota_groups[plan.id]))
        return out

    async def list_active_due(self, now: datetime | None = None) -> list[EntitlementPlan]:
        when = now or datetime.now(UTC)
        stmt = select(EntitlementPlan).where(
            EntitlementPlan.is_active.is_(True),
            EntitlementPlan.valid_until <= when,
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(
        self,
        *,
        scope: str,
        scope_id: uuid.UUID,
        label: str,
        valid_from: datetime,
        valid_until: datetime,
        included_models: list[str] | None = None,
        included_capabilities: list[str] | None = None,
        is_active: bool = True,
        auto_renew: bool = False,
        notes: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> EntitlementPlan:
        plan = EntitlementPlan(
            target_kind=scope,
            target_id=scope_id,
            label=label,
            included_models=list(included_models or []),
            included_capabilities=list(included_capabilities or []),
            valid_from=valid_from,
            valid_until=valid_until,
            is_active=is_active,
            auto_renew=auto_renew,
            notes=notes,
            extra=extra,
        )
        self._session.add(plan)
        await self._session.flush()
        return plan

    async def add_quota(
        self,
        *,
        plan_id: uuid.UUID,
        label: str,
        window_seconds: int,
        limit_usd: Any | None = None,
        limit_tokens: int | None = None,
        limit_requests: int | None = None,
        unit_price_usd_per_token: Any | None = None,
        unit_price_usd_per_request: Any | None = None,
        reset_strategy: str = "rolling",
    ) -> EntitlementPlanQuota:
        quota = EntitlementPlanQuota(
            plan_id=plan_id,
            label=label,
            window_seconds=window_seconds,
            reset_strategy=reset_strategy,
            limit_usd=limit_usd,
            limit_tokens=limit_tokens,
            limit_requests=limit_requests,
            unit_price_usd_per_token=unit_price_usd_per_token,
            unit_price_usd_per_request=unit_price_usd_per_request,
        )
        self._session.add(quota)
        await self._session.flush()
        return quota

    async def replace_quotas(
        self, plan_id: uuid.UUID, quotas: list[dict[str, Any]]
    ) -> list[EntitlementPlanQuota]:
        existing = await self._session.execute(
            select(EntitlementPlanQuota).where(EntitlementPlanQuota.plan_id == plan_id)
        )
        for row in existing.scalars().all():
            await self._session.delete(row)
        await self._session.flush()
        return [await self.add_quota(plan_id=plan_id, **q) for q in quotas]

    async def update(self, plan_id: uuid.UUID, **fields: Any) -> EntitlementPlan | None:
        plan = await self.get(plan_id)
        if plan is None:
            return None
        for k, v in fields.items():
            if hasattr(plan, k) and v is not None:
                setattr(plan, k, v)
        await self._session.flush()
        return plan

    async def delete(self, plan_id: uuid.UUID) -> bool:
        plan = await self.get(plan_id)
        if plan is None:
            return False
        await self._session.delete(plan)
        await self._session.flush()
        return True

    async def get_with_quotas(
        self, plan_id: uuid.UUID
    ) -> tuple[EntitlementPlan, list[EntitlementPlanQuota]] | None:
        plan = await self.get(plan_id)
        if plan is None:
            return None
        quotas = await self.list_quotas(plan_id)
        return plan, quotas


__all__ = [
    "ENTITLEMENT_SCOPE_APIKEY_GRANT",
    "ENTITLEMENT_SCOPE_VKEY",
    "EntitlementPlanRepository",
]
