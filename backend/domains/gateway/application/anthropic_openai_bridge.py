"""
Anthropic Messages API ↔ OpenAI Chat Completions（LiteLLM ``acompletion``）转换。

对外 ``POST /v1/messages`` 经本模块转为现有 ``ProxyUseCase.chat_completion`` 可消费的
OpenAI 形 body，响应再转回 Anthropic ``message`` JSON；流式输出 Anthropic SSE 事件序列。

**设计取舍**：LiteLLM 亦提供 ``litellm.anthropic.messages.acreate`` 等原生 Anthropic 通道；本实现
刻意经 **OpenAI 形 ``chat_completion`` → Router / ``acompletion``**，以便与既有虚拟 Key、
预算、限流、metadata 与回调日志 **单编排核** 对齐。若未来 Router 与 ``anthropic.messages`` 的
凭据注入完全打通，可再评估切换以减少手搓 JSON 映射。
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
import json
from typing import Any
import uuid

import orjson


def _normalize_message_content(content: str | list[Any] | None) -> str | list[dict[str, Any]]:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return str(content)
    out: list[dict[str, Any]] = []
    for block in content:
        if isinstance(block, str):
            out.append({"type": "text", "text": block})
            continue
        if not isinstance(block, Mapping):
            continue
        bt = block.get("type")
        if bt == "text":
            out.append({"type": "text", "text": str(block.get("text", ""))})
        else:
            msg = f"Unsupported Anthropic content block type: {bt!r}"
            raise ValueError(msg)
    if not out:
        return ""
    if len(out) == 1 and out[0]["type"] == "text":
        return out[0]["text"]
    return out


def _system_to_openai_messages(system: Any) -> list[dict[str, Any]]:
    if system is None or system == "":
        return []
    if isinstance(system, str):
        return [{"role": "system", "content": system}]
    if isinstance(system, list):
        texts: list[str] = []
        for block in system:
            if isinstance(block, Mapping) and block.get("type") == "text":
                texts.append(str(block.get("text", "")))
            elif isinstance(block, str):
                texts.append(block)
        merged = "\n\n".join(t for t in texts if t)
        if not merged:
            return []
        return [{"role": "system", "content": merged}]
    return []


def _anthropic_tools_to_openai(tools: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for tool in tools:
        if not isinstance(tool, Mapping):
            continue
        name = str(tool.get("name", "")).strip()
        if not name:
            continue
        desc = tool.get("description")
        schema = tool.get("input_schema")
        if not isinstance(schema, Mapping):
            schema = {"type": "object", "properties": {}}
        fn: dict[str, Any] = {"name": name, "parameters": dict(schema)}
        if desc is not None:
            fn["description"] = str(desc)
        out.append({"type": "function", "function": fn})
    return out


def _anthropic_tool_choice_to_openai(tool_choice: Any) -> Any:
    if tool_choice is None:
        return None
    if isinstance(tool_choice, str):
        return tool_choice
    if not isinstance(tool_choice, Mapping):
        return None
    tc_type = tool_choice.get("type")
    if tc_type == "auto":
        return "auto"
    if tc_type == "any":
        return "required"
    if tc_type == "none":
        return "none"
    if tc_type == "tool":
        name = tool_choice.get("name")
        if isinstance(name, str) and name:
            return {"type": "function", "function": {"name": name}}
    return None


def anthropic_messages_request_to_openai_chat(body: dict[str, Any]) -> dict[str, Any]:
    """Anthropic ``/v1/messages`` JSON → OpenAI ``chat/completions`` 形 JSON（供 LiteLLM）。"""
    model = str(body.get("model", "")).strip()
    if not model:
        raise ValueError("model is required")
    if "max_tokens" not in body:
        raise ValueError("max_tokens is required")
    max_tokens_raw = body["max_tokens"]
    try:
        max_tokens = int(max_tokens_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("max_tokens must be an integer") from exc
    if max_tokens < 1:
        raise ValueError("max_tokens must be >= 1")

    raw_messages = body.get("messages")
    if not isinstance(raw_messages, list) or not raw_messages:
        raise ValueError("messages is required")

    openai_messages: list[dict[str, Any]] = []
    openai_messages.extend(_system_to_openai_messages(body.get("system")))

    for idx, msg in enumerate(raw_messages):
        if not isinstance(msg, Mapping):
            raise ValueError(f"messages[{idx}] must be an object")
        role = msg.get("role")
        if role not in ("user", "assistant"):
            raise ValueError(f"messages[{idx}].role must be user or assistant")
        content = _normalize_message_content(msg.get("content"))
        openai_messages.append({"role": str(role), "content": content})

    out: dict[str, Any] = {
        "model": model,
        "messages": openai_messages,
        "max_tokens": max_tokens,
    }
    if body.get("stream"):
        out["stream"] = True
        out["stream_options"] = {"include_usage": True}
    if "temperature" in body and body["temperature"] is not None:
        out["temperature"] = body["temperature"]
    if "top_p" in body and body["top_p"] is not None:
        out["top_p"] = body["top_p"]
    if "metadata" in body and isinstance(body["metadata"], Mapping):
        out["metadata"] = dict(body["metadata"])
    stops = body.get("stop_sequences")
    if isinstance(stops, list) and stops:
        out["stop"] = [str(s) for s in stops if str(s).strip()]
    tools = body.get("tools")
    if isinstance(tools, list) and tools:
        otools = _anthropic_tools_to_openai(tools)
        if otools:
            out["tools"] = otools
        tc = _anthropic_tool_choice_to_openai(body.get("tool_choice"))
        if tc is not None:
            out["tool_choice"] = tc
    return out


def _openai_finish_to_anthropic_stop_reason(finish: str | None) -> str:
    if finish in (None, "", "stop"):
        return "end_turn"
    if finish == "length":
        return "max_tokens"
    if finish == "tool_calls":
        return "tool_use"
    if finish == "content_filter":
        return "end_turn"
    return "end_turn"


def openai_chat_completion_response_to_anthropic_message(
    openai_resp: dict[str, Any],
) -> dict[str, Any]:
    """单次 OpenAI chat completion 字典 → Anthropic ``message`` 对象。"""
    choices = openai_resp.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("OpenAI response missing choices")
    ch0 = choices[0]
    if not isinstance(ch0, Mapping):
        raise ValueError("OpenAI choice invalid")
    message = ch0.get("message")
    if not isinstance(message, Mapping):
        raise ValueError("OpenAI response missing message")
    finish = ch0.get("finish_reason")
    finish_s = str(finish) if finish is not None else None

    content_blocks: list[dict[str, Any]] = []
    tool_calls = message.get("tool_calls")
    if isinstance(tool_calls, list) and tool_calls:
        for tc in tool_calls:
            if not isinstance(tc, Mapping):
                continue
            fn = tc.get("function")
            if not isinstance(fn, Mapping):
                continue
            name = str(fn.get("name", ""))
            raw_args = fn.get("arguments", "{}")
            try:
                parsed = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            except json.JSONDecode:
                parsed = {"raw": raw_args}
            if not isinstance(parsed, dict):
                parsed = {"value": parsed}
            block: dict[str, Any] = {
                "type": "tool_use",
                "id": str(tc.get("id", f"toolu_{uuid.uuid4().hex[:24]}")),
                "name": name,
                "input": parsed,
            }
            content_blocks.append(block)
    text = message.get("content")
    if text:
        if isinstance(text, str) and text:
            content_blocks.insert(0, {"type": "text", "text": text})
        elif isinstance(text, list):
            for block in text:
                if isinstance(block, Mapping) and block.get("type") == "text":
                    content_blocks.insert(
                        0,
                        {"type": "text", "text": str(block.get("text", ""))},
                    )
                    break

    if not content_blocks:
        content_blocks.append({"type": "text", "text": ""})

    usage_in = openai_resp.get("usage")
    input_tokens = 0
    output_tokens = 0
    if isinstance(usage_in, Mapping):
        input_tokens = int(usage_in.get("prompt_tokens", 0) or 0)
        output_tokens = int(usage_in.get("completion_tokens", 0) or 0)

    oid = str(openai_resp.get("id") or "")
    msg_id = oid if oid.startswith("msg_") else f"msg_{uuid.uuid4().hex}"

    return {
        "id": msg_id,
        "type": "message",
        "role": "assistant",
        "model": str(openai_resp.get("model", "")),
        "content": content_blocks,
        "stop_reason": _openai_finish_to_anthropic_stop_reason(finish_s),
        "stop_sequence": None,
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_creation_input_tokens": None,
            "cache_read_input_tokens": None,
        },
    }


def _sse_event(event_name: str, payload: dict[str, Any]) -> bytes:
    line = orjson.dumps(payload).decode()
    return f"event: {event_name}\ndata: {line}\n\n".encode()


async def openai_chat_stream_chunks_to_anthropic_sse(
    chunks: AsyncIterator[dict[str, Any]],
    *,
    model: str,
    message_id: str,
) -> AsyncIterator[bytes]:
    """将 OpenAI 形流式 chunk 序列转为 Anthropic Messages SSE bytes。"""
    block_index = 0
    sent_block_start = False
    last_finish: str | None = None
    last_usage: dict[str, int] | None = None

    yield _sse_event(
        "message_start",
        {
            "type": "message_start",
            "message": {
                "id": message_id,
                "type": "message",
                "role": "assistant",
                "model": model,
                "content": [],
                "stop_reason": None,
                "stop_sequence": None,
                "usage": {"input_tokens": 0, "output_tokens": 0},
            },
        },
    )

    async for chunk in chunks:
        if not isinstance(chunk, dict):
            continue
        usage = chunk.get("usage")
        if isinstance(usage, Mapping):
            pt = usage.get("prompt_tokens")
            ct = usage.get("completion_tokens")
            if pt is not None or ct is not None:
                last_usage = {
                    "input_tokens": int(pt or 0),
                    "output_tokens": int(ct or 0),
                }

        choices = chunk.get("choices")
        if not isinstance(choices, list) or not choices:
            continue
        c0 = choices[0]
        if not isinstance(c0, dict):
            continue
        delta = c0.get("delta")
        d = delta if isinstance(delta, dict) else {}
        finish_reason = c0.get("finish_reason")

        piece = d.get("content")
        if piece:
            if not sent_block_start:
                yield _sse_event(
                    "content_block_start",
                    {
                        "type": "content_block_start",
                        "index": block_index,
                        "content_block": {"type": "text", "text": ""},
                    },
                )
                sent_block_start = True
            yield _sse_event(
                "content_block_delta",
                {
                    "type": "content_block_delta",
                    "index": block_index,
                    "delta": {"type": "text_delta", "text": str(piece)},
                },
            )

        if finish_reason:
            last_finish = str(finish_reason)

    if sent_block_start:
        yield _sse_event(
            "content_block_stop",
            {"type": "content_block_stop", "index": block_index},
        )

    usage_payload = last_usage or {"input_tokens": 0, "output_tokens": 0}
    yield _sse_event(
        "message_delta",
        {
            "type": "message_delta",
            "delta": {
                "stop_reason": _openai_finish_to_anthropic_stop_reason(last_finish),
                "stop_sequence": None,
            },
            "usage": usage_payload,
        },
    )
    yield _sse_event("message_stop", {"type": "message_stop"})


__all__ = [
    "anthropic_messages_request_to_openai_chat",
    "openai_chat_completion_response_to_anthropic_message",
    "openai_chat_stream_chunks_to_anthropic_sse",
]
