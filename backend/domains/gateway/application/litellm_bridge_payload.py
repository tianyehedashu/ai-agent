"""
LiteLLM kwargs 与 Gateway 桥接层之间的纯拆分逻辑。

供 ``LLMGateway``、单测或其它调用方复用，避免在 agent 域内重复维护
「pop 标准字段 + 剩余 extras」规则。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, cast


@dataclass(frozen=True, slots=True)
class ChatBridgePayload:
    """``acompletion`` kwargs → ``GatewayBridge.chat_completion`` 的已拆分参数。"""

    stream: bool
    model: str
    messages: list[dict[str, Any]]
    temperature: float
    max_tokens: int
    tools: Any
    tool_choice: Any
    response_format: Any
    api_key: str | None
    api_base: str | None
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class EmbeddingBridgePayload:
    """``aembedding`` kwargs → ``GatewayBridge.embedding`` 的已拆分参数。"""

    inputs: str | list[str]
    model: str
    api_key: str | None
    api_base: str | None
    extras: dict[str, Any] = field(default_factory=dict)


def split_chat_completion_for_bridge(
    litellm_kwargs: dict[str, Any],
) -> ChatBridgePayload | None:
    """从与 LiteLLM ``acompletion`` 一致的 kwargs 拆出桥接所需字段。

    若缺少 ``model`` 或 ``messages``（且 messages 不能为 None），返回 ``None``。
    其余未识别的键保留在 ``extras`` 中（如 ``extra_headers``、``endpoint_id``）。
    """
    kw = dict(litellm_kwargs)
    stream = bool(kw.pop("stream", False))
    model_val = kw.pop("model", None)
    messages_val = kw.pop("messages", None)
    if not model_val or messages_val is None:
        return None
    if not isinstance(messages_val, list):
        return None
    messages = cast("list[dict[str, Any]]", messages_val)

    temperature = float(kw.pop("temperature", 0.7))
    max_tokens = int(kw.pop("max_tokens", 4096))
    tools = kw.pop("tools", None)
    tool_choice = kw.pop("tool_choice", None)
    response_format = kw.pop("response_format", None)
    api_key = kw.pop("api_key", None)
    api_base = kw.pop("api_base", None)

    return ChatBridgePayload(
        stream=stream,
        model=str(model_val),
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        tools=tools,
        tool_choice=tool_choice,
        response_format=response_format,
        api_key=api_key,
        api_base=api_base,
        extras=dict(kw),
    )


def split_embedding_for_bridge(
    litellm_kwargs: dict[str, Any],
) -> EmbeddingBridgePayload | None:
    """从与 LiteLLM ``aembedding`` 一致的 kwargs 拆出桥接所需字段。"""
    kw = dict(litellm_kwargs)
    inputs = kw.pop("input", None)
    model_val = kw.pop("model", None)
    if inputs is None or not model_val:
        return None

    api_key = kw.pop("api_key", None)
    api_base = kw.pop("api_base", None)

    return EmbeddingBridgePayload(
        inputs=inputs,
        model=str(model_val),
        api_key=api_key,
        api_base=api_base,
        extras=dict(kw),
    )


__all__ = [
    "ChatBridgePayload",
    "EmbeddingBridgePayload",
    "split_chat_completion_for_bridge",
    "split_embedding_for_bridge",
]
