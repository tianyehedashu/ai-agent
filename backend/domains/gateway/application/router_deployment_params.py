"""按客户端模型名解析直连 LiteLLM 所需的 deployment 参数（与 Router 构建共用单价逻辑）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
import uuid

from domains.gateway.application.model_or_route_resolution import resolve_model_or_route
from domains.gateway.domain.policies.volcengine_image import parse_volcengine_image_endpoint_id
from domains.gateway.infrastructure.repositories.credential_repository import (
    ProviderCredentialRepository,
)
from libs.exceptions import ValidationError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from domains.gateway.infrastructure.router_singleton import PricingLookup


VOLCENGINE_IMAGE_ENDPOINT_PROBE_MESSAGE = (
    "未配置火山图像接入点（凭据 extra.image_endpoint_id 为空；"
    "需设置 VOLCENGINE_IMAGE_ENDPOINT_ID 或在 BYOK 凭据 extra 中提供）"
)

VOLCENGINE_IMAGE_ENDPOINT_PROXY_MESSAGE = (
    "volcengine image generation requires credential extra.image_endpoint_id "
    "(VOLCENGINE_IMAGE_ENDPOINT_ID or BYOK extra)"
)


@dataclass(frozen=True, slots=True)
class VolcengineImageDeployment:
    """火山生图直连所需的 deployment 参数与图像接入点。"""

    litellm_params: dict[str, Any]
    image_endpoint_id: str


async def load_bindable_credential(
    session: AsyncSession,
    credential_id: uuid.UUID,
) -> Any | None:
    """团队或系统凭据，且 ``is_active``。"""
    cred = await ProviderCredentialRepository(session).get(credential_id)
    if cred is None:
        from domains.gateway.infrastructure.repositories.system_credential_repository import (
            SystemProviderCredentialRepository,
        )

        cred = await SystemProviderCredentialRepository(session).get(credential_id)
    if cred is None or not cred.is_active:
        return None
    return cred


def require_volcengine_image_endpoint_id(
    extra: dict[str, Any] | None,
    *,
    message: str = VOLCENGINE_IMAGE_ENDPOINT_PROXY_MESSAGE,
) -> str:
    """从凭据 extra 解析图像接入点；缺失时抛 ``ValidationError``。"""
    endpoint = parse_volcengine_image_endpoint_id(extra)
    if endpoint is None:
        raise ValidationError(message)
    return endpoint


async def _resolved_record_and_credential(
    session: AsyncSession,
    team_id: uuid.UUID,
    client_model: str,
    *,
    user_id: uuid.UUID | None = None,
) -> tuple[Any, Any] | None:
    resolved = await resolve_model_or_route(session, team_id, client_model, user_id=user_id)
    if resolved is None:
        return None
    cred = await load_bindable_credential(session, resolved.record.credential_id)
    if cred is None:
        return None
    return resolved.record, cred


async def resolve_deployment_litellm_params(
    session: AsyncSession,
    team_id: uuid.UUID,
    client_model: str,
    *,
    user_id: uuid.UUID | None = None,
    pricing_lookup: PricingLookup | None = None,
) -> dict[str, Any] | None:
    """解析 ``GatewayModel`` / ``GatewayRoute`` 主选行，构造直连 ``litellm`` 的 kwargs 片段。"""
    from domains.gateway.infrastructure.router_singleton import (
        _build_litellm_params,
        _load_upstream_pricing_lookup,
        _pricing_for_model,
    )

    pair = await _resolved_record_and_credential(session, team_id, client_model, user_id=user_id)
    if pair is None:
        return None
    record, cred = pair
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
        upstream_call_shape=getattr(record, "upstream_call_shape", None),
        capability=str(record.capability) if record.capability is not None else None,
    )


async def resolve_volcengine_image_deployment(
    session: AsyncSession,
    team_id: uuid.UUID,
    client_model: str,
    *,
    user_id: uuid.UUID | None = None,
    pricing_lookup: PricingLookup | None = None,
) -> VolcengineImageDeployment | None:
    """单次模型解析 + 凭据加载，返回直连参数与 ``image_endpoint_id``。"""
    from domains.gateway.infrastructure.router_singleton import (
        _build_litellm_params,
        _load_upstream_pricing_lookup,
        _pricing_for_model,
    )

    pair = await _resolved_record_and_credential(session, team_id, client_model, user_id=user_id)
    if pair is None:
        return None
    record, cred = pair
    extra = cred.extra if isinstance(cred.extra, dict) else None
    image_endpoint_id = require_volcengine_image_endpoint_id(extra)
    lookup = pricing_lookup
    if lookup is None:
        lookup = await _load_upstream_pricing_lookup(session)
    pricing = _pricing_for_model(record, lookup)
    litellm_params = _build_litellm_params(
        real_model=record.real_model,
        provider=record.provider,
        credential=cred,
        rpm_limit=record.rpm_limit,
        tpm_limit=record.tpm_limit,
        tags=record.tags,
        pricing=pricing,
        upstream_call_shape=getattr(record, "upstream_call_shape", None),
        capability=str(record.capability) if record.capability is not None else None,
    )
    return VolcengineImageDeployment(
        litellm_params=litellm_params,
        image_endpoint_id=image_endpoint_id,
    )


__all__ = [
    "VOLCENGINE_IMAGE_ENDPOINT_PROBE_MESSAGE",
    "VOLCENGINE_IMAGE_ENDPOINT_PROXY_MESSAGE",
    "VolcengineImageDeployment",
    "load_bindable_credential",
    "require_volcengine_image_endpoint_id",
    "resolve_deployment_litellm_params",
    "resolve_volcengine_image_deployment",
]
