"""Gateway 代理工厂：集中获取 GatewayProxyProtocol 实现，供各域注入。"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from libs.gateway.protocol import GatewayProxyProtocol


def get_gateway_proxy() -> GatewayProxyProtocol:
    """返回进程内 Gateway 桥接实现（单例）。"""
    from domains.gateway.application.internal_bridge import get_gateway_bridge

    return get_gateway_bridge()
