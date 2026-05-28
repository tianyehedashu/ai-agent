"""ProviderPlanRepository - 上游套餐仓储

加载活跃套餐 + 多层 quotas 的二级映射，供 ProviderPlanGuard 使用；
管理面 CRUD 透过 GatewayManagementWriteService 中转，本仓储仅负责 SQL 层。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import and_, or_, select

from domains.gateway.infrastructure.models.provider_plan import (
    ProviderPlan,
    ProviderPlanQuota,
)

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


class ProviderPlanRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, plan_id: uuid.UUID) -> ProviderPlan | None:
        return await self._session.get(ProviderPlan, plan_id)

    async def list_for_credential(self, credential_id: uuid.UUID) -> list[ProviderPlan]:
        stmt = (
            select(ProviderPlan)
            .where(ProviderPlan.credential_id == credential_id)
            .order_by(ProviderPlan.valid_from.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_active_for_credential_model(
        self,
        credential_id: uuid.UUID,
        real_model: str | None,
        *,
        now: datetime | None = None,
    ) -> ProviderPlan | None:
        """优先返回精确匹配 (credential, real_model)，否则回退到 real_model IS NULL 的整凭据套餐。

        多条候选时取 ``valid_from`` 最新一条；过期 (``valid_until <= now``) 与停用都跳过。
        """
        when = now or datetime.now(UTC)
        clauses = [
            ProviderPlan.credential_id == credential_id,
            ProviderPlan.is_active.is_(True),
            ProviderPlan.valid_from <= when,
            ProviderPlan.valid_until > when,
        ]
        if real_model is not None:
            clauses.append(
                or_(
                    ProviderPlan.real_model == real_model,
                    ProviderPlan.real_model.is_(None),
                )
            )
        else:
            clauses.append(ProviderPlan.real_model.is_(None))
        stmt = (
            select(ProviderPlan)
            .where(and_(*clauses))
            .order_by(
                # 精确匹配优先（real_model 不为 NULL 时，real_model 等于 ``real_model`` 优先）
                ProviderPlan.real_model.is_(None).asc(),
                ProviderPlan.valid_from.desc(),
            )
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def list_quotas(self, plan_id: uuid.UUID) -> list[ProviderPlanQuota]:
        stmt = (
            select(ProviderPlanQuota)
            .where(ProviderPlanQuota.plan_id == plan_id)
            .order_by(ProviderPlanQuota.window_seconds.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_with_quotas_for_credential(
        self, credential_id: uuid.UUID
    ) -> list[tuple[ProviderPlan, list[ProviderPlanQuota]]]:
        stmt = (
            select(ProviderPlan)
            .where(ProviderPlan.credential_id == credential_id)
            .order_by(ProviderPlan.valid_from.desc())
        )
        plans = list((await self._session.execute(stmt)).scalars().all())
        if not plans:
            return []
        plan_ids = [p.id for p in plans]
        qstmt = (
            select(ProviderPlanQuota)
            .where(ProviderPlanQuota.plan_id.in_(plan_ids))
            .order_by(ProviderPlanQuota.window_seconds.asc())
        )
        rows = list((await self._session.execute(qstmt)).scalars().all())
        groups: dict[uuid.UUID, list[ProviderPlanQuota]] = {p.id: [] for p in plans}
        for q in rows:
            groups[q.plan_id].append(q)
        return [(p, groups[p.id]) for p in plans]

    async def list_with_quotas_for_credentials(
        self, credential_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, list[tuple[ProviderPlan, list[ProviderPlanQuota]]]]:
        """批量拉取多个凭据的上游 plan + quotas（消除 N+1）。"""
        if not credential_ids:
            return {}
        unique_ids = list(dict.fromkeys(credential_ids))
        stmt = (
            select(ProviderPlan)
            .where(ProviderPlan.credential_id.in_(unique_ids))
            .order_by(ProviderPlan.valid_from.desc())
        )
        plans = list((await self._session.execute(stmt)).scalars().all())
        if not plans:
            return {cid: [] for cid in unique_ids}
        plan_ids = [p.id for p in plans]
        qstmt = (
            select(ProviderPlanQuota)
            .where(ProviderPlanQuota.plan_id.in_(plan_ids))
            .order_by(ProviderPlanQuota.window_seconds.asc())
        )
        quota_rows = list((await self._session.execute(qstmt)).scalars().all())
        quota_groups: dict[uuid.UUID, list[ProviderPlanQuota]] = {p.id: [] for p in plans}
        for q in quota_rows:
            quota_groups[q.plan_id].append(q)
        out: dict[uuid.UUID, list[tuple[ProviderPlan, list[ProviderPlanQuota]]]] = {
            cid: [] for cid in unique_ids
        }
        for plan in plans:
            out[plan.credential_id].append((plan, quota_groups[plan.id]))
        return out

    async def list_active_due(self, now: datetime | None = None) -> list[ProviderPlan]:
        """到期需要 lifecycle 处理的活跃套餐（``valid_until <= now``）。"""
        when = now or datetime.now(UTC)
        stmt = select(ProviderPlan).where(
            ProviderPlan.is_active.is_(True),
            ProviderPlan.valid_until <= when,
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(
        self,
        *,
        credential_id: uuid.UUID,
        real_model: str | None,
        label: str,
        valid_from: datetime,
        valid_until: datetime,
        is_active: bool = True,
        auto_renew: bool = False,
        notes: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> ProviderPlan:
        plan = ProviderPlan(
            credential_id=credential_id,
            real_model=real_model,
            label=label,
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
        reset_strategy: str = "rolling",
    ) -> ProviderPlanQuota:
        quota = ProviderPlanQuota(
            plan_id=plan_id,
            label=label,
            window_seconds=window_seconds,
            reset_strategy=reset_strategy,
            limit_usd=limit_usd,
            limit_tokens=limit_tokens,
            limit_requests=limit_requests,
        )
        self._session.add(quota)
        await self._session.flush()
        return quota

    async def update(self, plan_id: uuid.UUID, **fields: Any) -> ProviderPlan | None:
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

    async def replace_quotas(
        self,
        plan_id: uuid.UUID,
        quotas: list[dict[str, Any]],
    ) -> list[ProviderPlanQuota]:
        """以原子方式覆盖一个套餐的 quotas（用于 PATCH）。"""
        existing = await self._session.execute(
            select(ProviderPlanQuota).where(ProviderPlanQuota.plan_id == plan_id)
        )
        for row in existing.scalars().all():
            await self._session.delete(row)
        await self._session.flush()
        return [await self.add_quota(plan_id=plan_id, **q) for q in quotas]

    async def get_with_quotas(
        self, plan_id: uuid.UUID
    ) -> tuple[ProviderPlan, list[ProviderPlanQuota]] | None:
        plan = await self.get(plan_id)
        if plan is None:
            return None
        quotas = await self.list_quotas(plan_id)
        return plan, quotas


__all__ = ["ProviderPlanRepository"]
