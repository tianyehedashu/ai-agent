"""按客户端模型名解析直连 LiteLLM 所需的 deployment 参数（与 Router 构建共用单价逻辑）。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
import uuid

from domains.gateway.application.model_or_route_resolution import resolve_model_or_route
from domains.gateway.infrastructure.repositories.credential_repository import (
    ProviderCredentialRepository,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from domains.gateway.infrastructure.router_singleton import PricingLookup


async def resolve_deployment_litellm_params(
    session: AsyncSession,
    team_id: uuid.UUID,
    client_model: str,
    *,
    user_id: uuid.UUID | None = None,
    pricing_lookup: PricingLookup | None = None,
) -> dict[str, Any] | None:
    """解析 ``GatewayModel`` / ``GatewayRoute`` 主选行，构造直连 ``litellm`` 的 kwargs 片段。

    与 ``resolve_model_or_route`` 一致；``pricing_lookup`` 缺省时按需加载 active 上游价。
    """
    from domains.gateway.infrastructure.router_singleton import (
        _build_litellm_params,
        _load_upstream_pricing_lookup,
        _pricing_for_model,
    )

    resolved = await resolve_model_or_route(
        session, team_id, client_model, user_id=user_id
    )
    if resolved is None:
        return None
    record = resolved.record
    cred = await ProviderCredentialRepository(session).get(record.credential_id)
    if cred is None:
        from domains.gateway.infrastructure.repositories.system_credential_repository import (
            SystemProviderCredentialRepository,
        )

        cred = await SystemProviderCredentialRepository(session).get(record.credential_id)
    if cred is None or not cred.is_active:
        return None
    lookup = pricing_lookup
    if lookup is None:
        lookup = await _load_upstream_pricing_lookup(session)
    pricing = _pricing_for_model(record, lookup)
    return _build_litellm_params(
        real_model=record.real_model,
        provider=record.provider,
        credential=cred,
        rpm_limit=record.rpm_limit,
        tpm_limit=record.tpm_limit,
        tags=record.tags,
        pricing=pricing,
    )


__all__ = ["resolve_deployment_litellm_params"]
