"""注册表模型 → 凭据展示名批量解析（列表 / 定价等读路径共用）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from domains.gateway.domain.policies.model_selection import registry_kind_for_merged_row
from domains.gateway.infrastructure.repositories.credential_repository import (
    ProviderCredentialRepository,
)
from domains.gateway.infrastructure.repositories.system_credential_repository import (
    SystemProviderCredentialRepository,
)

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

    from domains.gateway.infrastructure.models.gateway_model import GatewayModel
    from domains.gateway.infrastructure.models.system_gateway import SystemGatewayModel


async def build_credential_name_map_for_models(
    session: AsyncSession,
    models: list[GatewayModel | SystemGatewayModel],
) -> dict[uuid.UUID, str]:
    """为已加载的合并模型列表批量解析凭据名。"""
    team_cred_ids: list[uuid.UUID] = []
    system_cred_ids: list[uuid.UUID] = []
    for model in models:
        kind = registry_kind_for_merged_row(model)
        if kind == "team":
            team_cred_ids.append(model.credential_id)
        else:
            system_cred_ids.append(model.credential_id)

    names: dict[uuid.UUID, str] = {}
    if team_cred_ids:
        creds = await ProviderCredentialRepository(session).list_by_ids(team_cred_ids)
        names.update({c.id: c.name for c in creds})
    if system_cred_ids:
        creds = await SystemProviderCredentialRepository(session).list_by_ids(system_cred_ids)
        names.update({c.id: c.name for c in creds})
    return names


async def build_credential_profile_map_for_models(
    session: AsyncSession,
    models: list[GatewayModel | SystemGatewayModel],
) -> dict[uuid.UUID, str]:
    """为已加载的合并模型列表批量解析凭据 ``profile_id``（读侧能力推导）。"""
    team_cred_ids: list[uuid.UUID] = []
    system_cred_ids: list[uuid.UUID] = []
    for model in models:
        kind = registry_kind_for_merged_row(model)
        if kind == "team":
            team_cred_ids.append(model.credential_id)
        else:
            system_cred_ids.append(model.credential_id)

    profiles: dict[uuid.UUID, str] = {}
    if team_cred_ids:
        creds = await ProviderCredentialRepository(session).list_by_ids(team_cred_ids)
        for cred in creds:
            raw = getattr(cred, "profile_id", None)
            if isinstance(raw, str) and raw.strip():
                profiles[cred.id] = raw.strip()
    if system_cred_ids:
        creds = await SystemProviderCredentialRepository(session).list_by_ids(system_cred_ids)
        for cred in creds:
            raw = getattr(cred, "profile_id", None)
            if isinstance(raw, str) and raw.strip():
                profiles[cred.id] = raw.strip()
    return profiles


__all__ = [
    "build_credential_name_map_for_models",
    "build_credential_profile_map_for_models",
]
