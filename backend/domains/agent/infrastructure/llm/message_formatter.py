"""Agent 领域消息 → OpenAI Chat Completions 形。"""

from __future__ import annotations

from typing import Any

from domains.agent.domain.types import Message, ToolCall  # noqa: TC001 — 格式化运行期使用
from utils.tokens import count_tokens


def format_tool_calls(tool_calls: list[ToolCall]) -> list[dict[str, Any]]:
    return [
        {
            "id": tc.id,
            "type": "function",
            "function": {
                "name": tc.name,
                "arguments": str(tc.arguments) if isinstance(tc.arguments, dict) else tc.arguments,
            },
        }
        for tc in tool_calls
    ]


def format_message(message: Message) -> dict[str, Any]:
    result: dict[str, Any] = {"role": message.role.value}
    if message.content:
        result["content"] = message.content
    if message.tool_calls:
        result["tool_calls"] = format_tool_calls(message.tool_calls)
    if message.tool_call_id:
        result["tool_call_id"] = message.tool_call_id
    return result


def format_domain_messages(messages: list[Message]) -> list[dict[str, Any]]:
    return [format_message(msg) for msg in messages]


format_messages = format_domain_messages


def estimate_message_tokens(message: Message, model: str = "gpt-4") -> int:
    tokens = 4
    if message.content:
        tokens += count_tokens(message.content, model)
    if message.tool_calls:
        for tc in message.tool_calls:
            tokens += count_tokens(tc.name, model)
            tokens += count_tokens(str(tc.arguments), model)
            tokens += 8
    if message.tool_call_id:
        tokens += count_tokens(message.tool_call_id, model)
    return tokens


def estimate_messages_tokens(messages: list[Message], model: str = "gpt-4") -> int:
    return sum(estimate_message_tokens(msg, model) for msg in messages) + 2


__all__ = [
    "estimate_message_tokens",
    "estimate_messages_tokens",
    "format_domain_messages",
    "format_message",
    "format_messages",
    "format_tool_calls",
]
