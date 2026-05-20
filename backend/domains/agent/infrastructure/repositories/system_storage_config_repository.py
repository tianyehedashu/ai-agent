"""System Storage Config Repository。"""

from __future__ import annotations

from typing import Any
import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from domains.agent.infrastructure.models.system_storage_config import SystemStorageConfig


class SystemStorageConfigRepository:
    """平台存储配置仓储（singleton）。"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_active(self) -> SystemStorageConfig | None:
        result = await self.db.execute(
            select(SystemStorageConfig)
            .where(SystemStorageConfig.is_active.is_(True))
            .order_by(SystemStorageConfig.updated_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _deactivate_others(self, keep_id: uuid.UUID) -> None:
        await self.db.execute(
            update(SystemStorageConfig)
            .where(
                SystemStorageConfig.is_active.is_(True),
                SystemStorageConfig.id != keep_id,
            )
            .values(is_active=False)
        )

    async def upsert(
        self,
        *,
        updated_by: uuid.UUID | None = None,
        **fields: Any,
    ) -> SystemStorageConfig:
        row = await self.get_active()
        if row is None:
            row = SystemStorageConfig(updated_by=updated_by, **fields)
            self.db.add(row)
        else:
            for key, value in fields.items():
                if hasattr(row, key):
                    setattr(row, key, value)
            row.updated_by = updated_by
        await self.db.flush()
        if fields.get("is_active", row.is_active):
            await self._deactivate_others(row.id)
        await self.db.refresh(row)
        return row


__all__ = ["SystemStorageConfigRepository"]
