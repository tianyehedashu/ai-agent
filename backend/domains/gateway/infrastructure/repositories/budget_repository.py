"""GatewayBudgetRepository"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import and_, delete, or_, select, update

from domains.gateway.infrastructure.models.budget import GatewayBudget

if TYPE_CHECKING:
    from datetime import datetime
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

    from domains.gateway.domain.proxy_policy import BudgetCheckQuery


class BudgetRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get(self, budget_id: uuid.UUID) -> GatewayBudget | None:
        return await self._session.get(GatewayBudget, budget_id)

    async def list_for_target(
        self, target_kind: str, target_id: uuid.UUID | None
    ) -> list[GatewayBudget]:
        stmt = select(GatewayBudget).where(
            and_(
                GatewayBudget.target_kind == target_kind,
                GatewayBudget.target_id == target_id,
            )
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_for_target_ids(
        self,
        target_kind: str,
        target_ids: list[uuid.UUID],
    ) -> list[GatewayBudget]:
        if not target_ids:
            return []
        stmt = select(GatewayBudget).where(
            and_(
                GatewayBudget.target_kind == target_kind,
                GatewayBudget.target_id.in_(target_ids),
            )
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_many_by_plan(
        self,
        plan: tuple[BudgetCheckQuery, ...] | list[BudgetCheckQuery],
    ) -> dict[tuple[str, uuid.UUID | None, str, str | None], GatewayBudget]:
        """一次查询拉取预算扫描 plan 中的全部配置行。"""
        if not plan:
            return {}
        clauses = []
        for query in plan:
            if query.model_name is None:
                model_clause = GatewayBudget.model_name.is_(None)
            else:
                model_clause = GatewayBudget.model_name == query.model_name
            if query.target_id is None:
                target_clause = GatewayBudget.target_id.is_(None)
            else:
                target_clause = GatewayBudget.target_id == query.target_id
            clauses.append(
                and_(
                    GatewayBudget.target_kind == query.target_kind,
                    target_clause,
                    GatewayBudget.period == query.period,
                    model_clause,
                )
            )
        stmt = select(GatewayBudget).where(or_(*clauses))
        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())
        out: dict[tuple[str, uuid.UUID | None, str, str | None], GatewayBudget] = {}
        for row in rows:
            key = (row.target_kind, row.target_id, row.period, row.model_name)
            out[key] = row
        return out

    async def get_for(
        self,
        target_kind: str,
        target_id: uuid.UUID | None,
        period: str,
        *,
        model_name: str | None = None,
    ) -> GatewayBudget | None:
        if model_name is None:
            model_clause = GatewayBudget.model_name.is_(None)
        else:
            model_clause = GatewayBudget.model_name == model_name
        stmt = select(GatewayBudget).where(
            and_(
                GatewayBudget.target_kind == target_kind,
                GatewayBudget.target_id == target_id,
                GatewayBudget.period == period,
                model_clause,
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert(
        self,
        *,
        target_kind: str,
        target_id: uuid.UUID | None,
        period: str,
        model_name: str | None = None,
        limit_usd: Decimal | None = None,
        soft_limit_usd: Decimal | None = None,
        limit_tokens: int | None = None,
        limit_requests: int | None = None,
        reset_at: datetime | None = None,
    ) -> GatewayBudget:
        existing = await self.get_for(target_kind, target_id, period, model_name=model_name)
        if existing is None:
            budget = GatewayBudget(
                target_kind=target_kind,
                target_id=target_id,
                period=period,
                model_name=model_name,
                limit_usd=limit_usd,
                soft_limit_usd=soft_limit_usd,
                limit_tokens=limit_tokens,
                limit_requests=limit_requests,
                reset_at=reset_at,
            )
            self._session.add(budget)
            await self._session.flush()
            return budget
        existing.limit_usd = limit_usd
        existing.soft_limit_usd = soft_limit_usd
        existing.limit_tokens = limit_tokens
        existing.limit_requests = limit_requests
        if reset_at is not None:
            existing.reset_at = reset_at
        await self._session.flush()
        return existing

    async def batch_upsert(
        self,
        items: list[dict[str, object]],
    ) -> list[GatewayBudget]:
        """批量 upsert：先批量查询已存在记录，再批量插入/更新。

        items 中每项字典须含：target_kind, target_id, period, model_name,
        limit_usd, soft_limit_usd, limit_tokens, limit_requests, reset_at。
        返回结果顺序与输入 items 一致。
        """
        if not items:
            return []

        # 1. 批量查询已存在记录
        clauses = []
        for item in items:
            target_kind = item["target_kind"]
            target_id = item.get("target_id")
            period = item["period"]
            model_name = item.get("model_name")
            if model_name is None:
                clauses.append(
                    and_(
                        GatewayBudget.target_kind == target_kind,
                        GatewayBudget.target_id == target_id,
                        GatewayBudget.period == period,
                        GatewayBudget.model_name.is_(None),
                    )
                )
            else:
                clauses.append(
                    and_(
                        GatewayBudget.target_kind == target_kind,
                        GatewayBudget.target_id == target_id,
                        GatewayBudget.period == period,
                        GatewayBudget.model_name == model_name,
                    )
                )

        existing_rows: list[GatewayBudget] = []
        if clauses:
            stmt = select(GatewayBudget).where(or_(*clauses))
            result = await self._session.execute(stmt)
            existing_rows = list(result.scalars().all())

        existing_by_key: dict[tuple, GatewayBudget] = {}
        for row in existing_rows:
            key = (row.target_kind, row.target_id, row.period, row.model_name)
            existing_by_key[key] = row

        # 2. 分类：更新 vs 插入
        to_insert: list[GatewayBudget] = []
        results: list[GatewayBudget] = []

        for item in items:
            key = (
                item["target_kind"],
                item.get("target_id"),
                item["period"],
                item.get("model_name"),
            )
            existing = existing_by_key.get(key)
            if existing is not None:
                existing.limit_usd = item.get("limit_usd")
                existing.soft_limit_usd = item.get("soft_limit_usd")
                existing.limit_tokens = item.get("limit_tokens")
                existing.limit_requests = item.get("limit_requests")
                reset_at = item.get("reset_at")
                if reset_at is not None:
                    existing.reset_at = reset_at
                results.append(existing)
            else:
                budget = GatewayBudget(
                    target_kind=item["target_kind"],
                    target_id=item.get("target_id"),
                    period=item["period"],
                    model_name=item.get("model_name"),
                    limit_usd=item.get("limit_usd"),
                    soft_limit_usd=item.get("soft_limit_usd"),
                    limit_tokens=item.get("limit_tokens"),
                    limit_requests=item.get("limit_requests"),
                    reset_at=item.get("reset_at"),
                )
                to_insert.append(budget)
                results.append(budget)

        if to_insert:
            self._session.add_all(to_insert)
        await self._session.flush()
        return results

    async def settle_usage(
        self,
        budget_id: uuid.UUID,
        *,
        delta_usd: Decimal,
        delta_tokens: int,
        delta_requests: int,
    ) -> None:
        """正向结算：增加用量计数"""
        await self._session.execute(
            update(GatewayBudget)
            .where(GatewayBudget.id == budget_id)
            .values(
                current_usd=GatewayBudget.current_usd + delta_usd,
                current_tokens=GatewayBudget.current_tokens + delta_tokens,
                current_requests=GatewayBudget.current_requests + delta_requests,
            )
        )

    async def reset(self, budget_id: uuid.UUID) -> None:
        await self._session.execute(
            update(GatewayBudget)
            .where(GatewayBudget.id == budget_id)
            .values(current_usd=Decimal("0"), current_tokens=0, current_requests=0)
        )

    async def delete(self, budget_id: uuid.UUID) -> bool:
        budget = await self.get(budget_id)
        if budget is None:
            return False
        await self._session.delete(budget)
        await self._session.flush()
        return True

    async def delete_by_model_names(self, model_names: list[str]) -> int:
        """删除 model_name 命中的预算行（模型删除后孤儿清理）。"""
        if not model_names:
            return 0
        stmt = delete(GatewayBudget).where(GatewayBudget.model_name.in_(model_names))
        result = await self._session.execute(stmt)
        await self._session.flush()
        return int(result.rowcount or 0)


__all__ = ["BudgetRepository"]
