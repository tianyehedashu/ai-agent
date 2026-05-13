"""Gateway 代理工厂：集中获取 ``GatewayProxyProtocol`` 实现，供各域注入。"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from domains.gateway.application.ports import GatewayProxyProtocol


def get_gateway_proxy() -> GatewayProxyProtocol:
    """返回进程内 Gateway 桥接实现（单例）。"""
    # 延迟导入避免与 internal_bridge / proxy 的循环依赖
    from domains.gateway.application.internal_bridge import (  # pylint: disable=import-outside-toplevel
        get_gateway_bridge,
    )

    return get_gateway_bridge()


__all__ = ["get_gateway_proxy"]
