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


def _apply_period_reset_fields(row: GatewayBudget, item: dict[str, object]) -> None:
    if "period_timezone" in item and item["period_timezone"] is not None:
        row.period_timezone = str(item["period_timezone"])
    if "period_reset_minutes" in item and item["period_reset_minutes"] is not None:
        row.period_reset_minutes = int(item["period_reset_minutes"])  # type: ignore[arg-type]
    if "period_reset_day" in item and item["period_reset_day"] is not None:
        row.period_reset_day = int(item["period_reset_day"])  # type: ignore[arg-type]


def _apply_enablement_fields(row: GatewayBudget, item: dict[str, object]) -> None:
    """启用停用 + 起止时间：仅当 key 存在时写入（兼容部分字段更新）。"""
    if "enabled" in item and item["enabled"] is not None:
        row.enabled = bool(item["enabled"])
    if "valid_from" in item:
        row.valid_from = item["valid_from"]  # type: ignore[assignment]
    if "valid_until" in item:
        row.valid_until = item["valid_until"]  # type: ignore[assignment]


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
    ) -> dict[
        tuple[str, uuid.UUID | None, str, str | None, uuid.UUID | None, uuid.UUID | None],
        GatewayBudget,
    ]:
        """一次查询拉取预算扫描 plan 中的全部配置行。

        坐标含 ``credential_id`` 与 ``tenant_id``：均按 ``None``→``IS NULL`` / 非空→相等匹配。
        ``tenant_id`` 仅对成员总量/模型护栏行非空（按团队隔离）。
        """
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
            if query.credential_id is None:
                credential_clause = GatewayBudget.credential_id.is_(None)
            else:
                credential_clause = GatewayBudget.credential_id == query.credential_id
            if query.tenant_id is None:
                tenant_clause = GatewayBudget.tenant_id.is_(None)
            else:
                tenant_clause = GatewayBudget.tenant_id == query.tenant_id
            clauses.append(
                and_(
                    GatewayBudget.target_kind == query.target_kind,
                    target_clause,
                    GatewayBudget.period == query.period,
                    model_clause,
                    credential_clause,
                    tenant_clause,
                )
            )
        stmt = select(GatewayBudget).where(or_(*clauses))
        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())
        out: dict[
            tuple[str, uuid.UUID | None, str, str | None, uuid.UUID | None, uuid.UUID | None],
            GatewayBudget,
        ] = {}
        for row in rows:
            key = (
                row.target_kind,
                row.target_id,
                row.period,
                row.model_name,
                row.credential_id,
                row.tenant_id,
            )
            out[key] = row
        return out

    async def get_for(
        self,
        target_kind: str,
        target_id: uuid.UUID | None,
        period: str,
        *,
        model_name: str | None = None,
        credential_id: uuid.UUID | None = None,
        tenant_id: uuid.UUID | None = None,
    ) -> GatewayBudget | None:
        if model_name is None:
            model_clause = GatewayBudget.model_name.is_(None)
        else:
            model_clause = GatewayBudget.model_name == model_name
        if credential_id is None:
            credential_clause = GatewayBudget.credential_id.is_(None)
        else:
            credential_clause = GatewayBudget.credential_id == credential_id
        if tenant_id is None:
            tenant_clause = GatewayBudget.tenant_id.is_(None)
        else:
            tenant_clause = GatewayBudget.tenant_id == tenant_id
        stmt = select(GatewayBudget).where(
            and_(
                GatewayBudget.target_kind == target_kind,
                GatewayBudget.target_id == target_id,
                GatewayBudget.period == period,
                model_clause,
                credential_clause,
                tenant_clause,
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
        credential_id: uuid.UUID | None = None,
        tenant_id: uuid.UUID | None = None,
        limit_usd: Decimal | None = None,
        soft_limit_usd: Decimal | None = None,
        limit_tokens: int | None = None,
        limit_requests: int | None = None,
        limit_images: int | None = None,
        reset_at: datetime | None = None,
        period_timezone: str | None = None,
        period_reset_minutes: int | None = None,
        period_reset_day: int | None = None,
    ) -> GatewayBudget:
        period_reset_item: dict[str, object] = {
            "period_timezone": period_timezone,
            "period_reset_minutes": period_reset_minutes,
            "period_reset_day": period_reset_day,
        }
        existing = await self.get_for(
            target_kind,
            target_id,
            period,
            model_name=model_name,
            credential_id=credential_id,
            tenant_id=tenant_id,
        )
        if existing is None:
            budget = GatewayBudget(
                target_kind=target_kind,
                target_id=target_id,
                period=period,
                model_name=model_name,
                credential_id=credential_id,
                tenant_id=tenant_id,
                limit_usd=limit_usd,
                soft_limit_usd=soft_limit_usd,
                limit_tokens=limit_tokens,
                limit_requests=limit_requests,
                limit_images=limit_images,
                reset_at=reset_at,
            )
            _apply_period_reset_fields(budget, period_reset_item)
            self._session.add(budget)
            await self._session.flush()
            return budget
        existing.limit_usd = limit_usd
        existing.soft_limit_usd = soft_limit_usd
        existing.limit_tokens = limit_tokens
        existing.limit_requests = limit_requests
        existing.limit_images = limit_images
        if reset_at is not None:
            existing.reset_at = reset_at
        _apply_period_reset_fields(existing, period_reset_item)
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
            credential_id = item.get("credential_id")
            tenant_id = item.get("tenant_id")
            model_clause = (
                GatewayBudget.model_name.is_(None)
                if model_name is None
                else GatewayBudget.model_name == model_name
            )
            credential_clause = (
                GatewayBudget.credential_id.is_(None)
                if credential_id is None
                else GatewayBudget.credential_id == credential_id
            )
            tenant_clause = (
                GatewayBudget.tenant_id.is_(None)
                if tenant_id is None
                else GatewayBudget.tenant_id == tenant_id
            )
            clauses.append(
                and_(
                    GatewayBudget.target_kind == target_kind,
                    GatewayBudget.target_id == target_id,
                    GatewayBudget.period == period,
                    model_clause,
                    credential_clause,
                    tenant_clause,
                )
            )

        existing_rows: list[GatewayBudget] = []
        if clauses:
            stmt = select(GatewayBudget).where(or_(*clauses))
            result = await self._session.execute(stmt)
            existing_rows = list(result.scalars().all())

        existing_by_key: dict[tuple, GatewayBudget] = {}
        for row in existing_rows:
            key = (
                row.target_kind,
                row.target_id,
                row.period,
                row.model_name,
                row.credential_id,
                row.tenant_id,
            )
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
                item.get("credential_id"),
                item.get("tenant_id"),
            )
            existing = existing_by_key.get(key)
            if existing is not None:
                existing.limit_usd = item.get("limit_usd")
                existing.soft_limit_usd = item.get("soft_limit_usd")
                existing.limit_tokens = item.get("limit_tokens")
                existing.limit_requests = item.get("limit_requests")
                if "limit_images" in item:
                    existing.limit_images = item.get("limit_images")
                reset_at = item.get("reset_at")
                if reset_at is not None:
                    existing.reset_at = reset_at
                _apply_period_reset_fields(existing, item)
                _apply_enablement_fields(existing, item)
                results.append(existing)
            else:
                budget = GatewayBudget(
                    target_kind=item["target_kind"],
                    target_id=item.get("target_id"),
                    period=item["period"],
                    model_name=item.get("model_name"),
                    credential_id=item.get("credential_id"),
                    tenant_id=item.get("tenant_id"),
                    limit_usd=item.get("limit_usd"),
                    soft_limit_usd=item.get("soft_limit_usd"),
                    limit_tokens=item.get("limit_tokens"),
                    limit_requests=item.get("limit_requests"),
                    limit_images=item.get("limit_images"),
                    reset_at=item.get("reset_at"),
                )
                _apply_period_reset_fields(budget, item)
                _apply_enablement_fields(budget, item)
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
        delta_images: int = 0,
    ) -> None:
        """正向结算：增加用量计数"""
        values = {
            "current_usd": GatewayBudget.current_usd + delta_usd,
            "current_tokens": GatewayBudget.current_tokens + delta_tokens,
            "current_requests": GatewayBudget.current_requests + delta_requests,
        }
        if delta_images:
            values["current_images"] = GatewayBudget.current_images + delta_images
        await self._session.execute(
            update(GatewayBudget).where(GatewayBudget.id == budget_id).values(**values)
        )

    async def reset(self, budget_id: uuid.UUID) -> None:
        await self.set_usage(
            budget_id,
            current_usd=Decimal("0"),
            current_tokens=0,
            current_requests=0,
            current_images=0,
        )

    async def set_usage(
        self,
        budget_id: uuid.UUID,
        *,
        current_usd: Decimal,
        current_tokens: int,
        current_requests: int,
        current_images: int = 0,
    ) -> None:
        await self._session.execute(
            update(GatewayBudget)
            .where(GatewayBudget.id == budget_id)
            .values(
                current_usd=current_usd,
                current_tokens=current_tokens,
                current_requests=current_requests,
                current_images=current_images,
            )
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
