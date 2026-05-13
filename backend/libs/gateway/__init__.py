"""Gateway 服务抽象层 - 跨域 Gateway 调用的协议定义"""

from .factory import get_gateway_proxy
from .internal_actor import resolve_internal_gateway_user_id
from .litellm_payload import (
    ChatBridgePayload,
    EmbeddingBridgePayload,
    split_chat_completion_for_bridge,
    split_embedding_for_bridge,
)
from .protocol import (
    GatewayCallContext,
    GatewayProxyProtocol,
    GatewayResponse,
    GatewayStreamChunk,
)

__all__ = [
    "ChatBridgePayload",
    "EmbeddingBridgePayload",
    "GatewayCallContext",
    "GatewayProxyProtocol",
    "GatewayResponse",
    "GatewayStreamChunk",
    "get_gateway_proxy",
    "resolve_internal_gateway_user_id",
    "split_chat_completion_for_bridge",
    "split_embedding_for_bridge",
]
