"""GatewayVirtualKeyRepository"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import and_, select, update

from domains.gateway.infrastructure.models.virtual_key import GatewayVirtualKey

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


class VirtualKeyRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get(self, key_id: uuid.UUID) -> GatewayVirtualKey | None:
        return await self._session.get(GatewayVirtualKey, key_id)

    async def get_by_hash(self, key_hash: str) -> GatewayVirtualKey | None:
        stmt = select(GatewayVirtualKey).where(GatewayVirtualKey.key_hash == key_hash)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_key_id(self, key_id_str: str) -> GatewayVirtualKey | None:
        stmt = select(GatewayVirtualKey).where(GatewayVirtualKey.key_id == key_id_str)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_team(
        self,
        team_id: uuid.UUID,
        *,
        include_system: bool = False,
        include_inactive: bool = True,
    ) -> list[GatewayVirtualKey]:
        clauses = [GatewayVirtualKey.team_id == team_id]
        if not include_system:
            clauses.append(GatewayVirtualKey.is_system.is_(False))
        if not include_inactive:
            clauses.append(GatewayVirtualKey.is_active.is_(True))
        stmt = (
            select(GatewayVirtualKey)
            .where(and_(*clauses))
            .order_by(GatewayVirtualKey.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_or_create_system_key(
        self,
        team_id: uuid.UUID,
        *,
        encrypted_key: str,
        key_hash: str,
        key_id_str: str,
    ) -> GatewayVirtualKey:
        """获取该团队的 system key（用于内部桥接）"""
        stmt = select(GatewayVirtualKey).where(
            GatewayVirtualKey.team_id == team_id,
            GatewayVirtualKey.is_system.is_(True),
            GatewayVirtualKey.is_active.is_(True),
        )
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing is not None:
            return existing
        new_key = GatewayVirtualKey(
            team_id=team_id,
            created_by_user_id=None,
            name="__system_internal_bridge__",
            description="自动创建：内部模块调用桥接",
            key_id=key_id_str,
            key_hash=key_hash,
            encrypted_key=encrypted_key,
            allowed_models=[],
            allowed_capabilities=[],
            store_full_messages=False,
            guardrail_enabled=True,
            is_system=True,
            is_active=True,
        )
        self._session.add(new_key)
        await self._session.flush()
        return new_key

    async def create(
        self,
        *,
        team_id: uuid.UUID,
        created_by_user_id: uuid.UUID | None,
        name: str,
        description: str | None,
        key_id_str: str,
        key_hash: str,
        encrypted_key: str,
        allowed_models: list[str],
        allowed_capabilities: list[str],
        rpm_limit: int | None,
        tpm_limit: int | None,
        store_full_messages: bool,
        guardrail_enabled: bool,
        is_system: bool = False,
        expires_at: datetime | None = None,
    ) -> GatewayVirtualKey:
        new_key = GatewayVirtualKey(
            team_id=team_id,
            created_by_user_id=created_by_user_id,
            name=name,
            description=description,
            key_id=key_id_str,
            key_hash=key_hash,
            encrypted_key=encrypted_key,
            allowed_models=allowed_models,
            allowed_capabilities=allowed_capabilities,
            rpm_limit=rpm_limit,
            tpm_limit=tpm_limit,
            store_full_messages=store_full_messages,
            guardrail_enabled=guardrail_enabled,
            is_system=is_system,
            expires_at=expires_at,
        )
        self._session.add(new_key)
        await self._session.flush()
        return new_key

    async def revoke(self, key_id: uuid.UUID) -> bool:
        key = await self.get(key_id)
        if key is None:
            return False
        key.is_active = False
        await self._session.flush()
        return True

    async def touch_used(self, key_id: uuid.UUID) -> None:
        await self._session.execute(
            update(GatewayVirtualKey)
            .where(GatewayVirtualKey.id == key_id)
            .values(
                last_used_at=datetime.now(UTC),
                usage_count=GatewayVirtualKey.usage_count + 1,
            )
        )

    async def remove_model_names_from_all_allowed_lists(self, model_names: frozenset[str]) -> int:
        """从所有激活 vkey 的 ``allowed_models`` 中移除给定虚拟模型名（配置下线托管模型后修剪）。"""
        if not model_names:
            return 0
        stmt = select(GatewayVirtualKey).where(GatewayVirtualKey.is_active.is_(True))
        result = await self._session.execute(stmt)
        keys = list(result.scalars().all())
        changed = 0
        for key in keys:
            allowed = list(key.allowed_models or ())
            if not allowed:
                continue
            new_allowed = [m for m in allowed if m not in model_names]
            if new_allowed != allowed:
                key.allowed_models = new_allowed
                changed += 1
        if changed:
            await self._session.flush()
        return changed


__all__ = ["VirtualKeyRepository"]
