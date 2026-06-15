"""VirtualKeyTeamGrantRepository — 跨团队授权行 CRUD"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select, update

from domains.gateway.infrastructure.models.virtual_key_team_grant import (
    GatewayVirtualKeyTeamGrant,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
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

    async def batch_active_tenant_ids_by_vkeys(
        self, vkey_ids: Sequence[uuid.UUID]
    ) -> dict[uuid.UUID, tuple[uuid.UUID, ...]]:
        """管理面批量预取：vkey_id → active grant tenant_ids。"""
        if not vkey_ids:
            return {}
        stmt = select(
            GatewayVirtualKeyTeamGrant.vkey_id,
            GatewayVirtualKeyTeamGrant.tenant_id,
        ).where(
            GatewayVirtualKeyTeamGrant.vkey_id.in_(vkey_ids),
            GatewayVirtualKeyTeamGrant.is_active.is_(True),
        )
        result = await self._session.execute(stmt)
        grouped: dict[uuid.UUID, list[uuid.UUID]] = {}
        for vkey_id, tenant_id in result.all():
            grouped.setdefault(vkey_id, []).append(tenant_id)
        return {vid: tuple(tids) for vid, tids in grouped.items()}

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
        """幂等插入 active grant（先查后插，避免依赖 partial index 的 ON CONFLICT 方言差异）。"""
        existing = await self.get_active(vkey_id, tenant_id)
        if existing is not None:
            return existing

        grant = GatewayVirtualKeyTeamGrant(
            vkey_id=vkey_id,
            tenant_id=tenant_id,
            granted_by_user_id=granted_by_user_id,
            is_self=is_self,
            is_active=True,
        )
        self._session.add(grant)
        await self._session.flush()
        return grant

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
        """批量撤销某用户在指定 team 上的所有非自洽 grant。

        由 ``team_service.remove_member`` 同步调用；运维脚本 ``cleanup_stale_vkey_grants`` 复用同一逻辑。
        """
        from datetime import UTC
        from datetime import datetime as dt

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

    async def revoke_all_for_tenant(
        self,
        tenant_id: uuid.UUID,
        *,
        reason: str = "team_archived",
    ) -> int:
        """撤销指向某 team 的全部 active grant（含 is_self；团队删除时调用）。"""
        from datetime import UTC
        from datetime import datetime as dt

        stmt = (
            update(GatewayVirtualKeyTeamGrant)
            .where(
                GatewayVirtualKeyTeamGrant.tenant_id == tenant_id,
                GatewayVirtualKeyTeamGrant.is_active.is_(True),
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
