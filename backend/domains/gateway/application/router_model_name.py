"""代理层：客户端 ``model`` → Router ``model_name``（依赖解析结果）。"""

from __future__ import annotations

from typing import TYPE_CHECKING
import uuid

from domains.gateway.domain.router_model_name import encode_router_model_name

if TYPE_CHECKING:
    from domains.gateway.application.model_or_route_resolution import ResolvedModelName
    from domains.gateway.infrastructure.models.gateway_model import GatewayModel
    from domains.gateway.infrastructure.models.gateway_route import GatewayRoute


def router_model_name_for_gateway_model(model: GatewayModel) -> str:
    return encode_router_model_name(model.team_id, model.name)


def router_model_name_for_route(route: GatewayRoute) -> str:
    return encode_router_model_name(route.team_id, route.virtual_model)


def router_model_name_for_client(
    team_id: uuid.UUID,
    client_model: str,
    resolved: ResolvedModelName | None,
) -> str:
    """代理调用 Router 前：按解析结果选择编码后的 ``model`` 参数。"""
    cleaned = client_model.strip()
    if not cleaned:
        return cleaned
    if resolved is None:
        return cleaned
    if resolved.route is not None:
        return encode_router_model_name(team_id, cleaned)
    return encode_router_model_name(resolved.record.team_id, cleaned)


__all__ = [
    "router_model_name_for_client",
    "router_model_name_for_gateway_model",
    "router_model_name_for_route",
]
