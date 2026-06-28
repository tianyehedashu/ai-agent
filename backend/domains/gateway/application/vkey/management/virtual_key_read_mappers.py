"""GatewayVirtualKey ORM → VirtualKeyReadModel。"""

from __future__ import annotations

from typing import TYPE_CHECKING
import uuid

from domains.gateway.infrastructure.repositories.virtual_key_team_grant_repository import (
    VirtualKeyTeamGrantRepository,
)

from .virtual_key_read_model import VirtualKeyReadModel

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

    from domains.gateway.infrastructure.models.virtual_key import GatewayVirtualKey


def virtual_key_from_orm(
    record: GatewayVirtualKey,
    *,
    granted_team_ids: tuple[uuid.UUID, ...] | None = None,
) -> VirtualKeyReadModel:
    return VirtualKeyReadModel(
        id=record.id,
        tenant_id=record.tenant_id,
        team_id=record.tenant_id,
        name=record.name,
        description=record.description,
        masked_key_display=record.masked_key_display,
        allowed_models=tuple(record.allowed_models or ()),
        allowed_capabilities=tuple(record.allowed_capabilities or ()),
        rpm_limit=record.rpm_limit,
        tpm_limit=record.tpm_limit,
        store_full_messages=record.store_full_messages,
        guardrail_enabled=record.guardrail_enabled,
        is_system=record.is_system,
        is_active=record.is_active,
        expires_at=record.expires_at,
        last_used_at=record.last_used_at,
        usage_count=record.usage_count,
        created_at=record.created_at,
        encrypted_key=record.encrypted_key,
        granted_team_ids=granted_team_ids or (),
    )


async def virtual_keys_from_orm_with_grants(
    session: AsyncSession,
    records: Sequence[GatewayVirtualKey],
) -> list[VirtualKeyReadModel]:
    """批量映射 vkey 并预取 grants，避免列表 N+1。"""
    if not records:
        return []
    repo = VirtualKeyTeamGrantRepository(session)
    grants_by_vkey = await repo.batch_active_tenant_ids_by_vkeys([r.id for r in records])
    return [
        virtual_key_from_orm(r, granted_team_ids=grants_by_vkey.get(r.id, ())) for r in records
    ]


__all__ = ["virtual_key_from_orm", "virtual_keys_from_orm_with_grants"]
