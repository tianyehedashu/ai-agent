"""代理调用前解析下游价并写入 LiteLLM metadata / kwargs。"""

from __future__ import annotations

from typing import Any
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from domains.gateway.application.model_or_route_resolution import (
    ResolvedModelName,
    resolve_model_or_route,
)
from domains.gateway.application.pricing.pricing_management import build_pricing_service
from domains.gateway.application.pricing.pricing_service import (
    RateUnavailableError,
    downstream_rate_to_custom_cost,
)

_CUSTOM_PRICING_FIELD_NAMES: frozenset[str] = frozenset(
    {
        "input_cost_per_token",
        "output_cost_per_token",
        "cache_creation_input_token_cost",
        "cache_read_input_token_cost",
        "per_request_usd",
    }
)


def _custom_cost_from_metadata_field(
    metadata: dict[str, Any] | None,
    field: str,
    *,
    require_token_rates: bool = True,
) -> dict[str, float] | None:
    if not isinstance(metadata, dict):
        return None
    raw = metadata.get(field)
    if not isinstance(raw, dict):
        return None
    out: dict[str, float] = {}
    for key in _CUSTOM_PRICING_FIELD_NAMES:
        val = raw.get(key)
        if val is not None:
            out[key] = float(val)
    from domains.gateway.domain.policies.non_token_cost import NON_TOKEN_LITELLM_EXTRA_KEYS

    for key in NON_TOKEN_LITELLM_EXTRA_KEYS:
        val = raw.get(key)
        if val is not None:
            out[key] = float(val)
    if require_token_rates and (
        "input_cost_per_token" not in out or "output_cost_per_token" not in out
    ):
        if "per_request_usd" not in out and not any(k in out for k in NON_TOKEN_LITELLM_EXTRA_KEYS):
            return None
    return out or None


def downstream_custom_from_metadata(metadata: dict[str, Any] | None) -> dict[str, float] | None:
    """从 metadata 读取下游单价 dict（供 completion_cost / kwargs 注入）。"""
    return _custom_cost_from_metadata_field(metadata, "gateway_pricing_downstream")


def upstream_custom_from_metadata(metadata: dict[str, Any] | None) -> dict[str, float] | None:
    """从 metadata 读取上游单价 dict（供预算 / cost_usd 计算）。"""
    return _custom_cost_from_metadata_field(
        metadata,
        "gateway_pricing_upstream",
        require_token_rates=False,
    )


def apply_downstream_custom_pricing_kwargs(kwargs: dict[str, Any]) -> None:
    """把下游单价写入 LiteLLM 调用 kwargs，使 ``response_cost`` 按下游价计算。"""
    custom = downstream_custom_from_metadata(
        kwargs.get("metadata") if isinstance(kwargs.get("metadata"), dict) else None
    )
    if custom is None:
        return
    for key, value in custom.items():
        kwargs[key] = value
    meta = kwargs.get("metadata")
    if isinstance(meta, dict):
        model_info = meta.setdefault("model_info", {})
        if isinstance(model_info, dict):
            model_info.update(custom)


async def attach_downstream_pricing_metadata(
    session: AsyncSession,
    meta: dict[str, Any],
    *,
    team_id: uuid.UUID,
    virtual_model: str,
    entitlement_plan_id: uuid.UUID | None,
    billing_package: str | None,
    resolved: ResolvedModelName | None = None,
) -> None:
    """向 ``metadata`` 注入下游单价（供回调结算 revenue）。

    ``virtual_model`` 既支持 ``GatewayModel.name``（单 deployment），也支持
    ``GatewayRoute.virtual_model``（多 deployment）；后者以路由主选 ``GatewayModel``
    的 ``provider`` / ``real_model`` 作为定价基准，回调中真实 deployment 命中后由
    ``custom_logger`` 用 ``model_info`` 中的凭据归因覆写日志。
    """
    if billing_package is not None:
        meta["gateway_billing_package"] = billing_package

    resolved_name = resolved
    if resolved_name is None:
        resolved_name = await resolve_model_or_route(session, team_id, virtual_model)
    if resolved_name is None:
        return

    record = resolved_name.record
    model_id = record.id
    provider = record.provider
    real_model = record.real_model
    capability = record.capability
    meta["gateway_gateway_model_id"] = str(model_id)
    meta["gateway_provider"] = provider
    meta["gateway_upstream_model"] = real_model
    if resolved_name.via_route is not None:
        meta["gateway_via_route"] = resolved_name.via_route

    svc = build_pricing_service(session)
    try:
        pricing = await svc.resolve_downstream_rate(
            tenant_id=team_id,
            entitlement_plan_id=entitlement_plan_id,
            gateway_model_id=model_id,
            provider=provider,
            upstream_model=real_model,
            capability=capability,
        )
    except RateUnavailableError:
        return

    meta["gateway_pricing_downstream"] = downstream_rate_to_custom_cost(pricing.downstream)
    if pricing.upstream is not None:
        upstream_extra = (
            pricing.upstream_row.extra
            if pricing.upstream_row is not None and pricing.upstream_row.extra
            else None
        )
        meta["gateway_pricing_upstream"] = downstream_rate_to_custom_cost(
            pricing.upstream,
            extra=upstream_extra,
        )
    meta["gateway_pricing_hit_chain"] = pricing.hit_chain


__all__ = [
    "apply_downstream_custom_pricing_kwargs",
    "attach_downstream_pricing_metadata",
    "downstream_custom_from_metadata",
    "upstream_custom_from_metadata",
]
