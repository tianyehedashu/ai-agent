"""gateway_rollup_state 仓储。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import select

from domains.gateway.infrastructure.models.gateway_rollup_state import (
    _ROLLUP_STATE_SINGLETON_ID,
    GatewayRollupState,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class GatewayRollupStateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_last_rolled_at(self) -> datetime | None:
        row = await self._session.get(GatewayRollupState, _ROLLUP_STATE_SINGLETON_ID)
        return row.last_rolled_at if row is not None else None

    async def ensure_initial_watermark(self, *, default_lookback_hours: int = 48) -> datetime:
        row = await self._session.get(GatewayRollupState, _ROLLUP_STATE_SINGLETON_ID)
        if row is not None:
            return row.last_rolled_at
        now = datetime.now(UTC)
        initial = now.replace(minute=0, second=0, microsecond=0) - timedelta(
            hours=default_lookback_hours
        )
        self._session.add(
            GatewayRollupState(id=_ROLLUP_STATE_SINGLETON_ID, last_rolled_at=initial)
        )
        await self._session.flush()
        return initial

    async def set_last_rolled_at(self, value: datetime) -> None:
        row = await self._session.get(GatewayRollupState, _ROLLUP_STATE_SINGLETON_ID)
        if row is None:
            self._session.add(
                GatewayRollupState(id=_ROLLUP_STATE_SINGLETON_ID, last_rolled_at=value)
            )
        else:
            row.last_rolled_at = value
        await self._session.flush()

    async def read_for_update(self) -> datetime:
        stmt = (
            select(GatewayRollupState)
            .where(GatewayRollupState.id == _ROLLUP_STATE_SINGLETON_ID)
            .with_for_update()
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return await self.ensure_initial_watermark()
        return row.last_rolled_at


__all__ = ["GatewayRollupStateRepository"]
