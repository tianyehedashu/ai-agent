"""VirtualKeyTeamGrantRepository — 跨团队授权行 CRUD"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import and_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from domains.gateway.infrastructure.models.virtual_key_team_grant import (
    GatewayVirtualKeyTeamGrant,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


class VirtualKeyTeamGrantRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    # ─── 读 ────────────────────────────────────────────────────────────────

    async def list_active_tenant_ids(self, vkey_id: uuid.UUID) -> tuple[uuid.UUID, ...]:
        """鉴权热路径：返回该 vkey 所有 active grant 的 tenant_id（含自洽行）。"""
        stmt = (
            select(GatewayVirtualKeyTeamGrant.tenant_id)
            .where(
                GatewayVirtualKeyTeamGrant.vkey_id == vkey_id,
                GatewayVirtualKeyTeamGrant.is_active.is_(True),
            )
        )
        result = await self._session.execute(stmt)
        return tuple(result.scalars().all())

    async def list_active_for_vkey(
        self, vkey_id: uuid.UUID
    ) -> list[GatewayVirtualKeyTeamGrant]:
        """管理面：返回该 vkey 所有 active grant 行（含自洽行）。"""
        stmt = (
            select(GatewayVirtualKeyTeamGrant)
            .where(
                GatewayVirtualKeyTeamGrant.vkey_id == vkey_id,
                GatewayVirtualKeyTeamGrant.is_active.is_(True),
            )
            .order_by(GatewayVirtualKeyTeamGrant.created_at.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_active(
        self, vkey_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> GatewayVirtualKeyTeamGrant | None:
        """按 (vkey_id, tenant_id) 查 active 行。"""
        stmt = select(GatewayVirtualKeyTeamGrant).where(
            GatewayVirtualKeyTeamGrant.vkey_id == vkey_id,
            GatewayVirtualKeyTeamGrant.tenant_id == tenant_id,
            GatewayVirtualKeyTeamGrant.is_active.is_(True),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    # ─── 写 ────────────────────────────────────────────────────────────────

    async def upsert_active(
        self,
        *,
        vkey_id: uuid.UUID,
        tenant_id: uuid.UUID,
        granted_by_user_id: uuid.UUID,
        is_self: bool = False,
    ) -> GatewayVirtualKeyTeamGrant:
        """幂等插入 active grant。

        使用 INSERT ... ON CONFLICT DO NOTHING（依赖 partial unique index
        ``uq_vkey_team_grants_active``）。若已存在则直接 SELECT 返回。
        """
        insert_stmt = (
            pg_insert(GatewayVirtualKeyTeamGrant.__table__)
            .values(
                vkey_id=vkey_id,
                tenant_id=tenant_id,
                granted_by_user_id=granted_by_user_id,
                is_self=is_self,
                is_active=True,
            )
            .on_conflict_do_nothing(
                constraint="uq_vkey_team_grants_active",
            )
            .returning(GatewayVirtualKeyTeamGrant.__table__.c.id)
        )
        result = await self._session.execute(insert_stmt)
        inserted_id = result.scalar_one_or_none()
        if inserted_id is not None:
            await self._session.flush()
            return await self._session.get(GatewayVirtualKeyTeamGrant, inserted_id)  # type: ignore[return-value]

        # 已存在 → SELECT
        existing = await self.get_active(vkey_id, tenant_id)
        assert existing is not None  # noqa: S101
        return existing

    async def revoke(
        self,
        vkey_id: uuid.UUID,
        tenant_id: uuid.UUID,
        *,
        reason: str,
    ) -> bool:
        """软撤销一行 active grant。成功返回 True，无行返回 False。"""
        grant = await self.get_active(vkey_id, tenant_id)
        if grant is None:
            return False
        grant.revoke(reason)
        await self._session.flush()
        return True

    async def revoke_grants_for_user_team(
        self,
        *,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
        reason: str = "membership_lost",
    ) -> int:
        """批量撤销某用户在指定 team 上的所有非自洽 grant（离线清理 + 同步触发共用）。

        集合幂等；并发安全（重复 update 无副作用）。
        返回受影响行数。
        """
        from datetime import UTC, datetime as dt

        stmt = (
            update(GatewayVirtualKeyTeamGrant)
            .where(
                GatewayVirtualKeyTeamGrant.granted_by_user_id == user_id,
                GatewayVirtualKeyTeamGrant.tenant_id == tenant_id,
                GatewayVirtualKeyTeamGrant.is_active.is_(True),
                GatewayVirtualKeyTeamGrant.is_self.is_(False),
            )
            .values(
                is_active=False,
                revoked_at=dt.now(UTC),
                revoked_reason=reason,
            )
        )
        result = await self._session.execute(stmt)
        return result.rowcount  # type: ignore[return-value]


__all__ = ["VirtualKeyTeamGrantRepository"]
