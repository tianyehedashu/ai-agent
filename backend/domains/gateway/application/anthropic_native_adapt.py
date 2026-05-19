"""
Anthropic Messages 原生通道响应/流式适配（LiteLLM ``aanthropic_messages`` 输出）。

将 LiteLLM 返回的对象转为 Anthropic JSON 或 SSE bytes，并抽取 usage 供预算结算。
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from typing import Any

import orjson


def validate_anthropic_messages_body(body: Mapping[str, Any]) -> None:
    """校验 ``POST /v1/messages`` 请求体最小字段。"""
    model = str(body.get("model", "")).strip()
    if not model:
        raise ValueError("model is required")
    if "max_tokens" not in body:
        raise ValueError("max_tokens is required")
    try:
        max_tokens = int(body["max_tokens"])
    except (TypeError, ValueError) as exc:
        raise ValueError("max_tokens must be an integer") from exc
    if max_tokens < 1:
        raise ValueError("max_tokens must be >= 1")
    raw_messages = body.get("messages")
    if not isinstance(raw_messages, list) or not raw_messages:
        raise ValueError("messages is required")


def estimate_anthropic_request_tokens(body: Mapping[str, Any]) -> int:
    """粗略估算 Anthropic 请求 token（限流/预算预检）。"""
    total_chars = 0
    system = body.get("system")
    if isinstance(system, str):
        total_chars += len(system)
    elif isinstance(system, list):
        for block in system:
            if isinstance(block, Mapping) and block.get("type") == "text":
                total_chars += len(str(block.get("text", "")))
    for msg in body.get("messages") or []:
        if not isinstance(msg, Mapping):
            continue
        content = msg.get("content")
        if isinstance(content, str):
            total_chars += len(content)
        elif isinstance(content, list):
            for block in content:
                if not isinstance(block, Mapping):
                    continue
                bt = block.get("type")
                if bt == "text":
                    total_chars += len(str(block.get("text", "")))
                elif bt in ("image", "document", "tool_result", "tool_use"):
                    total_chars += 512
    return total_chars // 4 + int(body.get("max_tokens") or 0)


def anthropic_usage_total_tokens(usage: Any) -> int:
    """从 Anthropic ``usage`` 对象或 dict 得到结算用 token 总数（input + output）。"""
    if usage is None:
        return 0
    if isinstance(usage, Mapping):
        inp = int(usage.get("input_tokens") or 0)
        out = int(usage.get("output_tokens") or 0)
        return inp + out
    inp = int(getattr(usage, "input_tokens", 0) or 0)
    out = int(getattr(usage, "output_tokens", 0) or 0)
    return inp + out


def anthropic_response_to_dict(response: Any) -> dict[str, Any]:
    """LiteLLM Anthropic 响应 → 可 JSON 序列化的 dict。"""
    if isinstance(response, dict):
        return dict(response)
    for attr in ("model_dump", "dict"):
        method = getattr(response, attr, None)
        if callable(method):
            try:
                dumped = method()
                if isinstance(dumped, dict):
                    return dumped
            except Exception:
                continue
    return {}


def _sse_event(event_name: str, payload: dict[str, Any]) -> bytes:
    line = orjson.dumps(payload).decode()
    return f"event: {event_name}\ndata: {line}\n\n".encode()


def anthropic_stream_chunk_to_bytes(chunk: Any) -> bytes | None:
    """将 LiteLLM 流式 chunk 转为 Anthropic SSE bytes；无法识别时返回 None。"""
    if isinstance(chunk, bytes):
        return chunk
    if isinstance(chunk, str):
        text = chunk.strip()
        if text.startswith("event:"):
            return chunk.encode()
        return None
    data: dict[str, Any] | None
    if isinstance(chunk, dict):
        data = chunk
    else:
        data = anthropic_response_to_dict(chunk)
        if not data:
            return None
    event_type = data.get("type")
    if not isinstance(event_type, str) or not event_type:
        return None
    return _sse_event(event_type, data)


def _usage_dict_from_mapping(usage: Mapping[str, Any]) -> dict[str, int] | None:
    keys = (
        "input_tokens",
        "output_tokens",
        "cache_creation_input_tokens",
        "cache_read_input_tokens",
    )
    out: dict[str, int] = {}
    for key in keys:
        raw = usage.get(key)
        if raw is not None:
            out[key] = int(raw)
    if out:
        return out
    return None


def extract_usage_from_anthropic_stream_event(data: Mapping[str, Any]) -> dict[str, int] | None:
    """从 Anthropic SSE 事件抽取 usage 字典。

    支持事件：``message_start``（含 ``message.usage``）、``message_delta``（含 ``usage``）。

    返回字段（仅包含上游实际出现的键，缺省则不写入）：

    - ``input_tokens`` / ``output_tokens``
    - ``cache_creation_input_tokens`` / ``cache_read_input_tokens``

    注意：调用方不可假设固定键集；预算 token 计数应通过
    ``anthropic_usage_total_tokens`` 计算（仅累加 input + output，不重复计 cache）。
    无 usage 时返回 ``None``。
    """
    et = data.get("type")
    if et == "message_delta":
        usage = data.get("usage")
        if isinstance(usage, Mapping):
            return _usage_dict_from_mapping(usage)
    if et == "message_start":
        message = data.get("message")
        if isinstance(message, Mapping):
            usage = message.get("usage")
            if isinstance(usage, Mapping):
                return _usage_dict_from_mapping(usage)
    return None


async def iter_anthropic_sse_bytes(
    stream: AsyncIterator[Any],
) -> AsyncIterator[bytes]:
    """透传/规范化 LiteLLM Anthropic 流为 SSE bytes。"""
    async for chunk in stream:
        out = anthropic_stream_chunk_to_bytes(chunk)
        if out is not None:
            yield out


__all__ = [
    "anthropic_response_to_dict",
    "anthropic_stream_chunk_to_bytes",
    "anthropic_usage_total_tokens",
    "estimate_anthropic_request_tokens",
    "extract_usage_from_anthropic_stream_event",
    "iter_anthropic_sse_bytes",
    "validate_anthropic_messages_body",
]
