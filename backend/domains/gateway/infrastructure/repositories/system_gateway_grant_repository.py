"""SystemGatewayGrantRepository — 系统级可见性 ACL。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import or_, select

from domains.gateway.infrastructure.models.system_gateway import SystemGatewayGrant

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


class SystemGatewayGrantRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, grant_id: uuid.UUID) -> SystemGatewayGrant | None:
        return await self._session.get(SystemGatewayGrant, grant_id)

    async def list_for_subject(
        self,
        subject_kind: str,
        subject_id: uuid.UUID,
    ) -> list[SystemGatewayGrant]:
        stmt = (
            select(SystemGatewayGrant)
            .where(
                SystemGatewayGrant.subject_kind == subject_kind,
                SystemGatewayGrant.subject_id == subject_id,
            )
            .order_by(SystemGatewayGrant.target_kind, SystemGatewayGrant.target_id)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_enabled_for_targets(
        self,
        *,
        team_id: uuid.UUID,
        user_id: uuid.UUID | None,
    ) -> list[SystemGatewayGrant]:
        """一次查询拉取 team / user 命中的 enabled grants。"""
        target_clauses = [
            (SystemGatewayGrant.target_kind == "team")
            & (SystemGatewayGrant.target_id == team_id)
        ]
        if user_id is not None:
            target_clauses.append(
                (SystemGatewayGrant.target_kind == "user")
                & (SystemGatewayGrant.target_id == user_id)
            )
        stmt = select(SystemGatewayGrant).where(
            SystemGatewayGrant.enabled.is_(True),
            or_(*target_clauses),
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_for_target(
        self,
        target_kind: str,
        target_id: uuid.UUID,
    ) -> list[SystemGatewayGrant]:
        stmt = (
            select(SystemGatewayGrant)
            .where(
                SystemGatewayGrant.target_kind == target_kind,
                SystemGatewayGrant.target_id == target_id,
                SystemGatewayGrant.enabled.is_(True),
            )
            .order_by(SystemGatewayGrant.subject_kind, SystemGatewayGrant.subject_id)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def find_existing(
        self,
        *,
        subject_kind: str,
        subject_id: uuid.UUID,
        target_kind: str,
        target_id: uuid.UUID,
    ) -> SystemGatewayGrant | None:
        stmt = (
            select(SystemGatewayGrant)
            .where(
                SystemGatewayGrant.subject_kind == subject_kind,
                SystemGatewayGrant.subject_id == subject_id,
                SystemGatewayGrant.target_kind == target_kind,
                SystemGatewayGrant.target_id == target_id,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        subject_kind: str,
        subject_id: uuid.UUID,
        target_kind: str,
        target_id: uuid.UUID,
        granted_by: uuid.UUID,
        note: str | None = None,
        enabled: bool = True,
    ) -> SystemGatewayGrant:
        existing = await self.find_existing(
            subject_kind=subject_kind,
            subject_id=subject_id,
            target_kind=target_kind,
            target_id=target_id,
        )
        if existing is not None:
            if enabled and not existing.enabled:
                existing.enabled = True
                await self._session.flush()
            return existing
        row = SystemGatewayGrant(
            subject_kind=subject_kind,
            subject_id=subject_id,
            target_kind=target_kind,
            target_id=target_id,
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
    ) -> SystemGatewayGrant | None:
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


__all__ = ["SystemGatewayGrantRepository"]
