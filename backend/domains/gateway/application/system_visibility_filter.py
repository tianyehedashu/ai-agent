"""系统模型可见性：应用层 IO 编排（查 grants / 凭据，调用 domain 纯函数）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from domains.gateway.domain.policies.system_visibility import (
    SystemModelVisibilitySnapshot,
    snapshots_need_grant_lookup,
    visible_system_model_ids,
)
from domains.gateway.domain.visibility import Visibility
from domains.gateway.infrastructure.repositories.system_credential_repository import (
    SystemProviderCredentialRepository,
)
from domains.gateway.infrastructure.repositories.system_gateway_grant_repository import (
    SystemGatewayGrantRepository,
)

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

    from domains.gateway.infrastructure.models.system_gateway import (
        SystemGatewayModel,
        SystemProviderCredential,
    )


def _snapshots_from_rows(
    rows: list[SystemGatewayModel],
    credentials_by_id: dict[uuid.UUID, SystemProviderCredential],
) -> list[SystemModelVisibilitySnapshot]:
    out: list[SystemModelVisibilitySnapshot] = []
    for row in rows:
        cred = credentials_by_id.get(row.credential_id)
        cred_vis = cred.visibility if cred is not None else Visibility.PUBLIC.value
        out.append(
            SystemModelVisibilitySnapshot(
                model_id=row.id,
                credential_id=row.credential_id,
                model_visibility=row.visibility,
                credential_visibility=cred_vis,
            )
        )
    return out


async def load_system_credentials_by_ids(
    session: AsyncSession,
    credential_ids: set[uuid.UUID],
) -> dict[uuid.UUID, SystemProviderCredential]:
    if not credential_ids:
        return {}
    repo = SystemProviderCredentialRepository(session)
    rows = await repo.list_by_ids(credential_ids)
    return {row.id: row for row in rows}


async def filter_visible_system_gateway_models(
    session: AsyncSession,
    rows: list[SystemGatewayModel],
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID | None,
    credentials_by_id: dict[uuid.UUID, SystemProviderCredential] | None = None,
) -> list[SystemGatewayModel]:
    """按 team/user grants 过滤 system 模型行（无行时原样返回）。"""
    if not rows:
        return []
    cred_map = credentials_by_id
    if cred_map is None:
        cred_ids = {row.credential_id for row in rows}
        cred_map = await load_system_credentials_by_ids(session, cred_ids)
    snapshots = _snapshots_from_rows(rows, cred_map)
    if not snapshots_need_grant_lookup(snapshots):
        return rows

    grant_rows = await SystemGatewayGrantRepository(session).list_enabled_for_targets(
        team_id=tenant_id,
        user_id=user_id,
    )
    granted_keys = {(g.subject_kind, g.subject_id) for g in grant_rows}
    allowed_ids = visible_system_model_ids(snapshots, granted_keys)
    return [row for row in rows if row.id in allowed_ids]


__all__ = [
    "filter_visible_system_gateway_models",
    "load_system_credentials_by_ids",
]
