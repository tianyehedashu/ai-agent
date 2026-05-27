"""LangChain 消息 → OpenAI Chat Completions 形（Agent 基础设施适配）。"""

from __future__ import annotations

import json
from typing import Any, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage


class LiteLLMFunctionCall(TypedDict):
    name: str
    arguments: str


class LiteLLMToolCall(TypedDict):
    id: str
    type: str
    function: LiteLLMFunctionCall


class LiteLLMMessage(TypedDict, total=False):
    role: str
    content: str | None
    reasoning_content: str
    tool_calls: list[LiteLLMToolCall]
    tool_call_id: str


def convert_langchain_tool_call(tc: dict[str, Any]) -> LiteLLMToolCall:
    args = tc["args"]
    arguments = args if isinstance(args, str) else json.dumps(args, ensure_ascii=False)
    return LiteLLMToolCall(
        id=tc["id"],
        type="function",
        function=LiteLLMFunctionCall(name=tc["name"], arguments=arguments),
    )


def convert_langchain_message(msg: BaseMessage) -> LiteLLMMessage:
    if isinstance(msg, HumanMessage):
        return LiteLLMMessage(role="user", content=str(msg.content))
    if isinstance(msg, AIMessage):
        result = LiteLLMMessage(role="assistant", content=msg.content or "")
        reasoning = msg.additional_kwargs.get("reasoning_content")
        if reasoning is not None:
            result["reasoning_content"] = str(reasoning)
        if msg.tool_calls:
            result["tool_calls"] = [convert_langchain_tool_call(tc) for tc in msg.tool_calls]
        return result
    if isinstance(msg, ToolMessage):
        return LiteLLMMessage(
            role="tool",
            tool_call_id=msg.tool_call_id,
            content=str(msg.content),
        )
    return LiteLLMMessage(role="user", content=str(msg.content))


def convert_langchain_messages(
    messages: list[BaseMessage],
    system_prompt: str | None = None,
) -> list[LiteLLMMessage]:
    result: list[LiteLLMMessage] = []
    if system_prompt:
        result.append(LiteLLMMessage(role="system", content=system_prompt))
    for msg in messages:
        result.append(convert_langchain_message(msg))
    return result


__all__ = [
    "LiteLLMFunctionCall",
    "LiteLLMMessage",
    "LiteLLMToolCall",
    "convert_langchain_message",
    "convert_langchain_messages",
]
