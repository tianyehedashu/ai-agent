"""上下游套餐配额窗口用量汇总表写路径。"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert as pg_insert

from domains.gateway.infrastructure.models.quota_plan_usage_bucket import (
    GatewayQuotaPlanUsageBucket,
)

if TYPE_CHECKING:
    from decimal import Decimal
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

    from domains.gateway.domain.quota_plan import UsageBucketNamespace


class QuotaPlanUsageBucketRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def increment_bucket(
        self,
        ns: UsageBucketNamespace,
        plan_id: uuid.UUID,
        quota_id: uuid.UUID,
        window_start: datetime,
        *,
        delta_tokens: int,
        delta_requests: int,
        delta_cost_usd: Decimal,
        delta_images: int = 0,
    ) -> None:
        now = datetime.now(UTC)
        stmt = pg_insert(GatewayQuotaPlanUsageBucket).values(
            ns=ns,
            plan_id=plan_id,
            quota_id=quota_id,
            window_start=window_start,
            tokens=delta_tokens,
            requests=delta_requests,
            images=delta_images,
            cost_usd=delta_cost_usd,
            updated_at=now,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["ns", "plan_id", "quota_id", "window_start"],
            set_={
                "tokens": GatewayQuotaPlanUsageBucket.tokens + stmt.excluded.tokens,
                "requests": GatewayQuotaPlanUsageBucket.requests + stmt.excluded.requests,
                "images": GatewayQuotaPlanUsageBucket.images + stmt.excluded.images,
                "cost_usd": GatewayQuotaPlanUsageBucket.cost_usd + stmt.excluded.cost_usd,
                "updated_at": now,
            },
        )
        await self._session.execute(stmt)

    async def set_bucket(
        self,
        ns: UsageBucketNamespace,
        plan_id: uuid.UUID,
        quota_id: uuid.UUID,
        window_start: datetime,
        *,
        tokens: int,
        requests: int,
        cost_usd: Decimal,
        images: int = 0,
    ) -> None:
        """覆盖写入当前窗口用量（管理面手工校正）。"""
        now = datetime.now(UTC)
        stmt = pg_insert(GatewayQuotaPlanUsageBucket).values(
            ns=ns,
            plan_id=plan_id,
            quota_id=quota_id,
            window_start=window_start,
            tokens=tokens,
            requests=requests,
            images=images,
            cost_usd=cost_usd,
            updated_at=now,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["ns", "plan_id", "quota_id", "window_start"],
            set_={
                "tokens": tokens,
                "requests": requests,
                "images": images,
                "cost_usd": cost_usd,
                "updated_at": now,
            },
        )
        await self._session.execute(stmt)

    async def delete_stale_updated_before(self, updated_before: datetime) -> int:
        """删除 ``updated_at`` 早于阈值的行（活跃窗口会持续刷新 updated_at）。"""
        stmt = delete(GatewayQuotaPlanUsageBucket).where(
            GatewayQuotaPlanUsageBucket.updated_at < updated_before
        )
        result = await self._session.execute(stmt)
        return int(result.rowcount or 0)


__all__ = ["QuotaPlanUsageBucketRepository"]
