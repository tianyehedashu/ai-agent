"""代理层：客户端 ``model`` → Router ``model_name``（依赖解析结果）。"""

from __future__ import annotations

from typing import TYPE_CHECKING
import uuid

from domains.gateway.domain.route.router_model_name import (
    deployment_scope_team_id,
    encode_router_model_name,
)

if TYPE_CHECKING:
    from domains.gateway.application.catalog.model_or_route_resolution import ResolvedModelName
    from domains.gateway.infrastructure.models.gateway_model import GatewayModel
    from domains.gateway.infrastructure.models.gateway_route import GatewayRoute


def router_model_name_for_gateway_model(model: GatewayModel) -> str:
    return encode_router_model_name(deployment_scope_team_id(model), model.name)


def router_model_name_for_route(route: GatewayRoute) -> str:
    return encode_router_model_name(deployment_scope_team_id(route), route.virtual_model)


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
    # 委派（跨团队共享路由）：deployment 注册在消费团队 T 的命名空间下（gw/t/{T}/{别名}），
    # 上游凭据走 owner，但编码键须用 T + 客户端别名，才能命中 grant 装配的 deployment。
    if resolved.delegated_grant_team_id is not None:
        return encode_router_model_name(resolved.delegated_grant_team_id, cleaned)
    if resolved.route is not None:
        return encode_router_model_name(deployment_scope_team_id(resolved.route), cleaned)
    return encode_router_model_name(deployment_scope_team_id(resolved.record), cleaned)


__all__ = [
    "router_model_name_for_client",
    "router_model_name_for_gateway_model",
    "router_model_name_for_route",
]
