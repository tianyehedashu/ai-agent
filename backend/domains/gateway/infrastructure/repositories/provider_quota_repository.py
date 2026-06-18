"""ProviderQuotaRepository - 上游扁平配额规则仓储"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import and_, case, or_, select

from domains.gateway.infrastructure.models.provider_quota import ProviderQuota

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


class ProviderQuotaRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, rule_id: uuid.UUID) -> ProviderQuota | None:
        return await self._session.get(ProviderQuota, rule_id)

    async def get_many(self, rule_ids: list[uuid.UUID]) -> dict[uuid.UUID, ProviderQuota]:
        """单次查询批量取规则，供 callback 结算消除 N 次独立 session。"""
        if not rule_ids:
            return {}
        unique_ids = list(dict.fromkeys(rule_ids))
        stmt = select(ProviderQuota).where(ProviderQuota.id.in_(unique_ids))
        rows = (await self._session.execute(stmt)).scalars().all()
        return {row.id: row for row in rows}

    async def list_for_credential(self, credential_id: uuid.UUID) -> list[ProviderQuota]:
        stmt = (
            select(ProviderQuota)
            .where(ProviderQuota.credential_id == credential_id)
            .order_by(ProviderQuota.label.asc(), ProviderQuota.window_seconds.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_active_for_credential_model(
        self,
        credential_id: uuid.UUID,
        real_model: str | None,
        *,
        now: datetime | None = None,
    ) -> list[ProviderQuota]:
        """返回 (credential, real_model) 下所有候选规则：精确 real_model 优先，含整凭据行。"""
        _ = now or datetime.now(UTC)
        clauses = [ProviderQuota.credential_id == credential_id]
        if real_model is not None:
            clauses.append(
                or_(
                    ProviderQuota.real_model == real_model,
                    ProviderQuota.real_model.is_(None),
                )
            )
            rank = case((ProviderQuota.real_model == real_model, 0), else_=1)
            order_by = (rank.asc(), ProviderQuota.label.asc(), ProviderQuota.window_seconds.asc())
        else:
            clauses.append(ProviderQuota.real_model.is_(None))
            order_by = (ProviderQuota.label.asc(), ProviderQuota.window_seconds.asc())
        stmt = select(ProviderQuota).where(and_(*clauses)).order_by(*order_by)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_for_credentials(
        self, credential_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, list[ProviderQuota]]:
        if not credential_ids:
            return {}
        unique_ids = list(dict.fromkeys(credential_ids))
        stmt = (
            select(ProviderQuota)
            .where(ProviderQuota.credential_id.in_(unique_ids))
            .order_by(ProviderQuota.label.asc(), ProviderQuota.window_seconds.asc())
        )
        rows = list((await self._session.execute(stmt)).scalars().all())
        out: dict[uuid.UUID, list[ProviderQuota]] = {cid: [] for cid in unique_ids}
        for row in rows:
            out[row.credential_id].append(row)
        return out

    async def upsert(
        self,
        *,
        credential_id: uuid.UUID,
        real_model: str | None,
        label: str,
        window_seconds: int,
        reset_strategy: str,
        reset_timezone: str,
        reset_time_minutes: int,
        reset_day_of_month: int,
        limit_usd: Any | None = None,
        limit_tokens: int | None = None,
        limit_requests: int | None = None,
        enabled: bool = True,
        valid_from: Any | None = None,
        valid_until: Any | None = None,
    ) -> ProviderQuota:
        stmt = select(ProviderQuota).where(
            ProviderQuota.credential_id == credential_id,
            ProviderQuota.label == label,
            ProviderQuota.real_model.is_(None)
            if real_model is None
            else ProviderQuota.real_model == real_model,
        )
        existing = (await self._session.execute(stmt)).scalar_one_or_none()
        if existing is not None:
            existing.window_seconds = window_seconds
            existing.reset_strategy = reset_strategy
            existing.reset_timezone = reset_timezone
            existing.reset_time_minutes = reset_time_minutes
            existing.reset_day_of_month = reset_day_of_month
            existing.limit_usd = limit_usd
            existing.limit_tokens = limit_tokens
            existing.limit_requests = limit_requests
            existing.enabled = enabled
            existing.valid_from = valid_from
            existing.valid_until = valid_until
            await self._session.flush()
            return existing

        row = ProviderQuota(
            credential_id=credential_id,
            real_model=real_model,
            label=label,
            window_seconds=window_seconds,
            reset_strategy=reset_strategy,
            reset_timezone=reset_timezone,
            reset_time_minutes=reset_time_minutes,
            reset_day_of_month=reset_day_of_month,
            limit_usd=limit_usd,
            limit_tokens=limit_tokens,
            limit_requests=limit_requests,
            enabled=enabled,
            valid_from=valid_from,
            valid_until=valid_until,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def set_enabled(self, rule_id: uuid.UUID, *, enabled: bool) -> bool:
        row = await self.get(rule_id)
        if row is None:
            return False
        row.enabled = enabled
        await self._session.flush()
        return True

    async def delete(self, rule_id: uuid.UUID) -> bool:
        row = await self.get(rule_id)
        if row is None:
            return False
        await self._session.delete(row)
        await self._session.flush()
        return True


__all__ = ["ProviderQuotaRepository"]
