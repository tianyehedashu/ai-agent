"""租户 + 系统模型合并列表与按名解析（可见性在应用层编排）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from domains.gateway.application.system_visibility_filter import (
    filter_visible_system_gateway_models,
)
from domains.gateway.domain.policies.model_selection import (
    merge_named_rows_team_granted_system,
    merge_named_rows_tenant_overrides_system,
    registry_kind_for_merged_row,
)
from domains.gateway.application.resource_grant_filter import (
    list_granted_personal_models_for_team,
)
from domains.gateway.infrastructure.models.gateway_model import GatewayModel
from domains.gateway.infrastructure.models.system_gateway import SystemGatewayModel
from domains.gateway.infrastructure.repositories.model_repository import GatewayModelRepository

GatewayRegistryModelRow = GatewayModel | SystemGatewayModel

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


async def _registry_row_deployable(
    session: AsyncSession,
    row: GatewayRegistryModelRow,
) -> bool:
    """与 Router ``_models_to_deployments`` 对齐：enabled 且凭据存在且 active。"""
    if not row.enabled:
        return False
    if registry_kind_for_merged_row(row) == "team":
        from domains.gateway.infrastructure.repositories.credential_repository import (
            ProviderCredentialRepository,
        )

        cred = await ProviderCredentialRepository(session).get(row.credential_id)
        return cred is not None and cred.is_active
    from domains.gateway.infrastructure.repositories.system_credential_repository import (
        SystemProviderCredentialRepository,
    )

    cred = await SystemProviderCredentialRepository(session).get(row.credential_id)
    return cred is not None and cred.is_active


async def list_merged_models_for_tenant(
    session: AsyncSession,
    tenant_id: uuid.UUID | None,
    *,
    only_enabled: bool = True,
    capability: str | None = None,
    provider: str | None = None,
    credential_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    apply_visibility_filter: bool = True,
) -> list[GatewayRegistryModelRow]:
    """``tenant_id is None`` 仅 system；否则 tenant 行 + system 行合并（tenant 同名优先）。"""
    repo = GatewayModelRepository(session)
    if tenant_id is None:
        return list(
            await repo.list_system(
                only_enabled=only_enabled,
                capability=capability,
                provider=provider,
                credential_id=credential_id,
            )
        )
    tenant_rows = await repo.list_tenant_owned(
        tenant_id,
        only_enabled=only_enabled,
        capability=capability,
        provider=provider,
        credential_id=credential_id,
    )
    system_rows = await repo.list_system(
        only_enabled=only_enabled,
        capability=capability,
        provider=provider,
        credential_id=credential_id,
    )
    if apply_visibility_filter and system_rows:
        system_rows = await filter_visible_system_gateway_models(
            session,
            system_rows,
            tenant_id=tenant_id,
            user_id=user_id,
        )
    granted_rows = await list_granted_personal_models_for_team(
        session,
        tenant_id,
        only_enabled=only_enabled,
    )
    return merge_named_rows_team_granted_system(
        tenant_rows,
        granted_rows,
        system_rows,
        only_enabled=only_enabled,
    )


async def resolve_by_name_visible(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    name: str,
    *,
    user_id: uuid.UUID | None = None,
) -> GatewayRegistryModelRow | None:
    """租户行优先；system 行经可见性策略过滤（代理入站须用此入口）。

    已禁用或凭据未激活的租户行不参与代理解析（与 Router 注册条件一致），避免遮蔽
    同名 system 行或阻断 ``resolve_model_or_route`` 的 personal team 回退。
    """
    repo = GatewayModelRepository(session)
    tenant_row = await repo.get_by_name(tenant_id, name)
    if tenant_row is not None and await _registry_row_deployable(session, tenant_row):
        return tenant_row

    from domains.gateway.application.resource_grant_resolution import (
        resolve_granted_model_by_name,
    )

    granted_row = await resolve_granted_model_by_name(
        session,
        tenant_id,
        name,
        strict_ambiguity=True,
    )
    if granted_row is not None and await _registry_row_deployable(session, granted_row):
        return granted_row

    system_row = await repo.get_system_by_name(name)
    if system_row is None or not await _registry_row_deployable(session, system_row):
        return None
    visible = await filter_visible_system_gateway_models(
        session,
        [system_row],
        tenant_id=tenant_id,
        user_id=user_id,
    )
    return visible[0] if visible else None


async def list_callable_system_model_names(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    user_id: uuid.UUID | None = None,
) -> list[str]:
    """callable 合并结果里仅 system 注册表的模型名（已应用可见性）。"""
    merged = await list_merged_models_for_tenant(
        session,
        tenant_id,
        only_enabled=True,
        user_id=user_id,
        apply_visibility_filter=True,
    )
    return [m.name for m in merged if registry_kind_for_merged_row(m) == "system"]


__all__ = [
    "GatewayRegistryModelRow",
    "_registry_row_deployable",
    "list_callable_system_model_names",
    "list_merged_models_for_tenant",
    "resolve_by_name_visible",
]
