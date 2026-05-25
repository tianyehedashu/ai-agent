"""系统模型可见性：应用层 IO 编排（查 grants / 凭据，调用 domain 纯函数）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from domains.gateway.domain.policies.system_visibility import (
    SystemModelVisibilitySnapshot,
    snapshots_need_grant_lookup,
    visible_system_model_ids,
)
from domains.gateway.domain.visibility import Visibility, credential_visibility_for_api
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


def system_credential_visible_to_subject(
    credential_id: uuid.UUID,
    credential_visibility: str,
    granted_keys: set[tuple[str, uuid.UUID]],
) -> bool:
    """凭据级 restricted 需 credential grant；public / 缺省对全员可见。"""
    if credential_visibility_for_api(credential_visibility) != "restricted":
        return True
    return ("credential", credential_id) in granted_keys


def system_credentials_need_grant_lookup(
    rows: list[SystemProviderCredential],
) -> bool:
    return any(
        credential_visibility_for_api(row.visibility) == "restricted" for row in rows
    )


async def filter_visible_system_provider_credentials(
    session: AsyncSession,
    rows: list[SystemProviderCredential],
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID | None,
    is_platform_admin: bool,
) -> list[SystemProviderCredential]:
    """按凭据 visibility + grants 过滤 system 凭据摘要/列表。"""
    if is_platform_admin or not rows:
        return list(rows)
    if not system_credentials_need_grant_lookup(rows):
        return list(rows)
    grant_rows = await SystemGatewayGrantRepository(session).list_enabled_for_targets(
        team_id=tenant_id,
        user_id=user_id,
    )
    granted_keys = {(g.subject_kind, g.subject_id) for g in grant_rows}
    return [
        row
        for row in rows
        if system_credential_visible_to_subject(row.id, row.visibility or Visibility.PUBLIC.value, granted_keys)
    ]


__all__ = [
    "filter_visible_system_gateway_models",
    "filter_visible_system_provider_credentials",
    "load_system_credentials_by_ids",
    "system_credential_visible_to_subject",
    "system_credentials_need_grant_lookup",
]
