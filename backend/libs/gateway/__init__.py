"""Gateway 服务抽象层 - 跨域 Gateway 调用的协议定义"""

from .protocol import (
    GatewayCallContext,
    GatewayProxyProtocol,
    GatewayResponse,
    GatewayStreamChunk,
)

__all__ = [
    "GatewayCallContext",
    "GatewayProxyProtocol",
    "GatewayResponse",
    "GatewayStreamChunk",
]
