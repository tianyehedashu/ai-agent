"""个人资源 grant 读侧。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from domains.gateway.application.grant.resource_grant_filter import (
    list_granted_personal_models_for_team,
    list_grants_for_owner,
)

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

    from domains.gateway.infrastructure.models.resource_grant import GatewayResourceGrant


@dataclass(frozen=True, slots=True)
class GrantedModelRead:
    model_id: uuid.UUID
    name: str
    real_model: str
    provider: str
    capability: str
    credential_id: uuid.UUID
    owner_user_id: uuid.UUID
    personal_team_id: uuid.UUID


async def list_owner_grants(
    session: AsyncSession,
    owner_user_id: uuid.UUID,
) -> list[GatewayResourceGrant]:
    return await list_grants_for_owner(session, owner_user_id)


async def list_team_granted_models(
    session: AsyncSession,
    target_team_id: uuid.UUID,
) -> list[GrantedModelRead]:
    from domains.gateway.application.grant.resource_grant_filter import (
        grant_cache_entry_for_team,
        owner_for_team,
    )

    models = await list_granted_personal_models_for_team(session, target_team_id)
    entry = await grant_cache_entry_for_team(session, target_team_id)
    return [
        GrantedModelRead(
            model_id=row.id,
            name=row.name,
            real_model=row.real_model,
            provider=row.provider,
            capability=row.capability,
            credential_id=row.credential_id,
            owner_user_id=owner_for_team(entry, row.tenant_id),
            personal_team_id=row.tenant_id,
        )
        for row in models
        if row.tenant_id is not None
    ]


__all__ = [
    "GrantedModelRead",
    "list_owner_grants",
    "list_team_granted_models",
]
