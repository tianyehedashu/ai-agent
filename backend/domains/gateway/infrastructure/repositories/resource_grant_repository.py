"""GatewayResourceGrantRepository — 个人资源 → 团队授权。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import delete, select

from domains.gateway.infrastructure.models.resource_grant import GatewayResourceGrant

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


class GatewayResourceGrantRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, grant_id: uuid.UUID) -> GatewayResourceGrant | None:
        return await self._session.get(GatewayResourceGrant, grant_id)

    async def list_enabled_for_team(self, target_team_id: uuid.UUID) -> list[GatewayResourceGrant]:
        stmt = (
            select(GatewayResourceGrant)
            .where(
                GatewayResourceGrant.target_team_id == target_team_id,
                GatewayResourceGrant.enabled.is_(True),
            )
            .order_by(GatewayResourceGrant.owner_user_id, GatewayResourceGrant.subject_kind)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_for_owner(
        self,
        owner_user_id: uuid.UUID,
        *,
        enabled_only: bool = False,
    ) -> list[GatewayResourceGrant]:
        stmt = select(GatewayResourceGrant).where(
            GatewayResourceGrant.owner_user_id == owner_user_id,
        )
        if enabled_only:
            stmt = stmt.where(GatewayResourceGrant.enabled.is_(True))
        stmt = stmt.order_by(
            GatewayResourceGrant.target_team_id,
            GatewayResourceGrant.subject_kind,
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_for_subject(
        self,
        subject_kind: str,
        subject_id: uuid.UUID,
    ) -> list[GatewayResourceGrant]:
        stmt = (
            select(GatewayResourceGrant)
            .where(
                GatewayResourceGrant.subject_kind == subject_kind,
                GatewayResourceGrant.subject_id == subject_id,
            )
            .order_by(GatewayResourceGrant.target_team_id)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def find_existing(
        self,
        *,
        subject_kind: str,
        subject_id: uuid.UUID,
        target_team_id: uuid.UUID,
    ) -> GatewayResourceGrant | None:
        stmt = (
            select(GatewayResourceGrant)
            .where(
                GatewayResourceGrant.subject_kind == subject_kind,
                GatewayResourceGrant.subject_id == subject_id,
                GatewayResourceGrant.target_team_id == target_team_id,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        owner_user_id: uuid.UUID,
        subject_kind: str,
        subject_id: uuid.UUID,
        target_team_id: uuid.UUID,
        granted_by: uuid.UUID,
        note: str | None = None,
        enabled: bool = True,
    ) -> GatewayResourceGrant:
        existing = await self.find_existing(
            subject_kind=subject_kind,
            subject_id=subject_id,
            target_team_id=target_team_id,
        )
        if existing is not None:
            if enabled and not existing.enabled:
                existing.enabled = True
                existing.granted_by = granted_by
                if note is not None:
                    existing.note = note
                await self._session.flush()
            return existing
        row = GatewayResourceGrant(
            owner_user_id=owner_user_id,
            subject_kind=subject_kind,
            subject_id=subject_id,
            target_team_id=target_team_id,
            granted_by=granted_by,
            note=note,
            enabled=enabled,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def update(
        self,
        grant_id: uuid.UUID,
        *,
        enabled: bool | None = None,
        note: str | None = None,
    ) -> GatewayResourceGrant | None:
        row = await self.get(grant_id)
        if row is None:
            return None
        if enabled is not None:
            row.enabled = enabled
        if note is not None:
            row.note = note
        await self._session.flush()
        return row

    async def delete(self, grant_id: uuid.UUID) -> bool:
        row = await self.get(grant_id)
        if row is None:
            return False
        await self._session.delete(row)
        await self._session.flush()
        return True

    async def delete_by_subject_ids(
        self,
        subject_kind: str,
        subject_ids: list[uuid.UUID],
    ) -> int:
        if not subject_ids:
            return 0
        stmt = delete(GatewayResourceGrant).where(
            GatewayResourceGrant.subject_kind == subject_kind,
            GatewayResourceGrant.subject_id.in_(subject_ids),
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return int(result.rowcount or 0)

    async def delete_by_owner_and_target(
        self,
        owner_user_id: uuid.UUID,
        target_team_id: uuid.UUID,
    ) -> int:
        stmt = delete(GatewayResourceGrant).where(
            GatewayResourceGrant.owner_user_id == owner_user_id,
            GatewayResourceGrant.target_team_id == target_team_id,
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return int(result.rowcount or 0)


__all__ = ["GatewayResourceGrantRepository"]
