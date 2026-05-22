"""租户 + 系统模型合并列表与按名解析（可见性在应用层编排）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from domains.gateway.application.system_visibility_filter import (
    filter_visible_system_gateway_models,
)
from domains.gateway.domain.policies.model_selection import (
    merge_named_rows_tenant_overrides_system,
    registry_kind_for_merged_row,
)
from domains.gateway.infrastructure.models.gateway_model import GatewayModel
from domains.gateway.infrastructure.models.system_gateway import SystemGatewayModel
from domains.gateway.infrastructure.repositories.model_repository import GatewayModelRepository

GatewayRegistryModelRow = GatewayModel | SystemGatewayModel

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


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
    return merge_named_rows_tenant_overrides_system(
        tenant_rows,
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
    """租户行优先；system 行经可见性策略过滤（代理入站须用此入口）。"""
    repo = GatewayModelRepository(session)
    record = await repo.resolve_by_name(tenant_id, name)
    if record is None:
        return None
    if registry_kind_for_merged_row(record) == "team":
        return record
    visible = await filter_visible_system_gateway_models(
        session,
        [record],
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
    "list_callable_system_model_names",
    "list_merged_models_for_tenant",
    "resolve_by_name_visible",
]
