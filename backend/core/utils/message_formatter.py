"""
Message Formatter - 消息格式化工具

提供统一的消息格式化函数，避免各模块重复实现。

支持的格式化操作：
- Message 对象转 LLM API 格式（OpenAI/Anthropic 兼容）
- LangChain BaseMessage 转 LiteLLM 格式
- ToolCall 对象转字典格式
- Token 估算
"""

import json
from typing import Any, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage

from core.types import Message, ToolCall
from utils.tokens import count_tokens

# ============================================================================
# LiteLLM 消息类型定义 (TypedDict 提供类型安全)
# ============================================================================


class LiteLLMFunctionCall(TypedDict):
    """LiteLLM 函数调用格式"""

    name: str
    arguments: str


class LiteLLMToolCall(TypedDict):
    """LiteLLM 工具调用格式"""

    id: str
    type: str  # 通常是 "function"
    function: LiteLLMFunctionCall


class LiteLLMMessage(TypedDict, total=False):
    """
    LiteLLM 消息格式

    total=False 表示所有字段都是可选的，因为不同角色的消息有不同字段。
    """

    role: str  # "system" | "user" | "assistant" | "tool"
    content: str | None
    tool_calls: list[LiteLLMToolCall]
    tool_call_id: str


# ============================================================================
# LangChain -> LiteLLM 消息转换
# ============================================================================


def convert_langchain_tool_call(tc: dict[str, Any]) -> LiteLLMToolCall:
    """
    将 LangChain ToolCall 转换为 LiteLLM 格式

    Args:
        tc: LangChain 的 ToolCall 字典 (TypedDict)

    Returns:
        LiteLLM 格式的工具调用
    """
    args = tc["args"]
    arguments = args if isinstance(args, str) else json.dumps(args, ensure_ascii=False)

    return LiteLLMToolCall(
        id=tc["id"],
        type="function",
        function=LiteLLMFunctionCall(
            name=tc["name"],
            arguments=arguments,
        ),
    )


def convert_langchain_message(msg: BaseMessage) -> LiteLLMMessage:
    """
    将 LangChain BaseMessage 转换为 LiteLLM 消息格式

    Args:
        msg: LangChain 消息 (HumanMessage, AIMessage, ToolMessage 等)

    Returns:
        LiteLLM 格式的消息字典
    """
    if isinstance(msg, HumanMessage):
        return LiteLLMMessage(role="user", content=str(msg.content))

    if isinstance(msg, AIMessage):
        result = LiteLLMMessage(role="assistant", content=msg.content or "")
        if msg.tool_calls:
            result["tool_calls"] = [convert_langchain_tool_call(tc) for tc in msg.tool_calls]
        return result

    if isinstance(msg, ToolMessage):
        return LiteLLMMessage(
            role="tool",
            tool_call_id=msg.tool_call_id,
            content=str(msg.content),
        )

    # 默认处理
    return LiteLLMMessage(role="user", content=str(msg.content))


def convert_langchain_messages(
    messages: list[BaseMessage],
    system_prompt: str | None = None,
) -> list[LiteLLMMessage]:
    """
    将 LangChain 消息列表转换为 LiteLLM 格式

    Args:
        messages: LangChain 消息列表
        system_prompt: 可选的系统提示（会添加到消息列表开头）

    Returns:
        LiteLLM 格式的消息列表
    """
    result: list[LiteLLMMessage] = []

    if system_prompt:
        result.append(LiteLLMMessage(role="system", content=system_prompt))

    for msg in messages:
        result.append(convert_langchain_message(msg))

    return result


def format_tool_calls(tool_calls: list[ToolCall]) -> list[dict[str, Any]]:
    """
    格式化工具调用列表为 OpenAI API 兼容格式

    Args:
        tool_calls: ToolCall 对象列表

    Returns:
        格式化后的字典列表
    """
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
    """
    格式化单条消息为 LLM API 格式

    Args:
        message: Message 对象

    Returns:
        格式化后的字典
    """
    result: dict[str, Any] = {"role": message.role.value}

    if message.content:
        result["content"] = message.content

    if message.tool_calls:
        result["tool_calls"] = format_tool_calls(message.tool_calls)

    if message.tool_call_id:
        result["tool_call_id"] = message.tool_call_id

    return result


def format_messages(messages: list[Message]) -> list[dict[str, Any]]:
    """
    格式化消息列表为 LLM API 格式

    Args:
        messages: Message 对象列表

    Returns:
        格式化后的字典列表
    """
    return [format_message(msg) for msg in messages]


def estimate_message_tokens(message: Message, model: str = "gpt-4") -> int:
    """
    估算单条消息的 Token 数量

    包含消息格式的额外开销（约 4 tokens）。

    Args:
        message: Message 对象
        model: 模型名称（用于选择编码器）

    Returns:
        预估的 Token 数量
    """
    tokens = 4  # 消息格式开销（role、分隔符等）

    if message.content:
        tokens += count_tokens(message.content, model)

    if message.tool_calls:
        for tc in message.tool_calls:
            tokens += count_tokens(tc.name, model)
            tokens += count_tokens(str(tc.arguments), model)
            tokens += 8  # 工具调用格式开销（id、type、function 等）

    if message.tool_call_id:
        tokens += count_tokens(message.tool_call_id, model)

    return tokens


def estimate_messages_tokens(messages: list[Message], model: str = "gpt-4") -> int:
    """
    估算消息列表的总 Token 数量

    Args:
        messages: Message 对象列表
        model: 模型名称

    Returns:
        预估的总 Token 数量
    """
    total = sum(estimate_message_tokens(msg, model) for msg in messages)
    # 回复开始的额外 Token
    total += 2
    return total
