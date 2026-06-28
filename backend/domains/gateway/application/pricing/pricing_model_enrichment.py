"""定价目录：gateway_model_id → 注册名 / 凭据 批量解析。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domains.gateway.domain.catalog.model_selection import registry_kind_for_merged_row
from domains.gateway.infrastructure.models.gateway_model import GatewayModel
from domains.gateway.infrastructure.models.system_gateway import SystemGatewayModel
from domains.gateway.infrastructure.repositories.credential_repository import (
    ProviderCredentialRepository,
)
from domains.gateway.infrastructure.repositories.system_credential_repository import (
    SystemProviderCredentialRepository,
)

RegistryKind = Literal["team", "system"]


@dataclass(frozen=True)
class PricingModelRef:
    gateway_model_id: uuid.UUID
    model_name: str
    provider: str
    credential_id: uuid.UUID
    credential_name: str | None
    registry_kind: RegistryKind
    real_model: str
    capability: str


async def build_pricing_model_ref_map(
    session: AsyncSession,
    model_ids: set[uuid.UUID],
    *,
    tenant_id: uuid.UUID | None = None,
) -> dict[uuid.UUID, PricingModelRef]:
    """批量解析注册表行与凭据名；未命中 id 不在 map 中。

    ``tenant_id`` 非空时，团队模型仅限该租户，避免跨租户泄露注册名/凭据。
    """
    if not model_ids:
        return {}

    ids = list(model_ids)
    team_clauses: list[object] = [GatewayModel.id.in_(ids)]
    if tenant_id is not None:
        team_clauses.append(GatewayModel.tenant_id == tenant_id)
    team_stmt = select(GatewayModel).where(*team_clauses)
    team_result = await session.execute(team_stmt)
    team_rows = list(team_result.scalars().all())
    found: dict[uuid.UUID, GatewayModel | SystemGatewayModel] = {r.id: r for r in team_rows}

    missing = [mid for mid in ids if mid not in found]
    if missing:
        sys_stmt = select(SystemGatewayModel).where(SystemGatewayModel.id.in_(missing))
        sys_result = await session.execute(sys_stmt)
        for row in sys_result.scalars().all():
            found[row.id] = row

    team_cred_ids: list[uuid.UUID] = []
    system_cred_ids: list[uuid.UUID] = []
    for row in found.values():
        kind = registry_kind_for_merged_row(row)
        if kind == "team":
            team_cred_ids.append(row.credential_id)
        else:
            system_cred_ids.append(row.credential_id)

    team_cred_names: dict[uuid.UUID, str] = {}
    if team_cred_ids:
        creds = await ProviderCredentialRepository(session).list_by_ids(team_cred_ids)
        team_cred_names = {c.id: c.name for c in creds}

    system_cred_names: dict[uuid.UUID, str] = {}
    if system_cred_ids:
        creds = await SystemProviderCredentialRepository(session).list_by_ids(system_cred_ids)
        system_cred_names = {c.id: c.name for c in creds}

    out: dict[uuid.UUID, PricingModelRef] = {}
    for model_id, row in found.items():
        kind = registry_kind_for_merged_row(row)
        cred_name = (
            team_cred_names.get(row.credential_id)
            if kind == "team"
            else system_cred_names.get(row.credential_id)
        )
        out[model_id] = PricingModelRef(
            gateway_model_id=model_id,
            model_name=row.name,
            provider=row.provider,
            credential_id=row.credential_id,
            credential_name=cred_name,
            registry_kind=kind,
            real_model=row.real_model,
            capability=row.capability,
        )
    return out


async def resolve_pricing_model_ref(
    session: AsyncSession,
    gateway_model_id: uuid.UUID,
    *,
    tenant_id: uuid.UUID | None = None,
) -> PricingModelRef | None:
    """按 id 解析单条注册行（tenant 表受 tenant_id 约束，再 fallback system 表）。"""
    refs = await build_pricing_model_ref_map(
        session,
        {gateway_model_id},
        tenant_id=tenant_id,
    )
    return refs.get(gateway_model_id)


__all__ = [
    "PricingModelRef",
    "build_pricing_model_ref_map",
    "resolve_pricing_model_ref",
]
