"""
Token Utilities - Token 计算工具
"""

from typing import Any

import tiktoken


def count_tokens(text: str, model: str = "gpt-4") -> int:
    """
    计算文本的 Token 数量

    使用 tiktoken 库进行计算
    """
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        # 回退到 cl100k_base
        encoding = tiktoken.get_encoding("cl100k_base")

    return len(encoding.encode(text))


def count_messages_tokens(messages: list[dict[str, Any]], model: str = "gpt-4") -> int:
    """
    计算消息列表的 Token 数量

    包含消息格式的额外 Token
    """
    total = 0

    for message in messages:
        # 每条消息有 4 个额外的 Token
        total += 4

        for key, value in message.items():
            if isinstance(value, str):
                total += count_tokens(value, model)
            elif isinstance(value, list):
                # 处理工具调用等列表
                total += count_tokens(str(value), model)

    # 回复开始的额外 Token
    total += 2

    return total


def truncate_to_token_limit(
    text: str,
    max_tokens: int,
    model: str = "gpt-4",
) -> str:
    """
    截断文本到指定 Token 限制
    """
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")

    tokens = encoding.encode(text)

    if len(tokens) <= max_tokens:
        return text

    truncated_tokens = tokens[:max_tokens]
    return encoding.decode(truncated_tokens)


def estimate_cost(
    input_tokens: int,
    output_tokens: int,
    model: str = "gpt-4",
) -> float:
    """
    估算 API 调用成本 (USD)

    基于常见模型的定价
    """
    pricing = {
        "gpt-4": {"input": 0.03, "output": 0.06},  # per 1K tokens
        "gpt-4-turbo": {"input": 0.01, "output": 0.03},
        "gpt-3.5-turbo": {"input": 0.0015, "output": 0.002},
        "claude-3-opus": {"input": 0.015, "output": 0.075},
        "claude-3-sonnet": {"input": 0.003, "output": 0.015},
        "claude-3-haiku": {"input": 0.00025, "output": 0.00125},
    }

    # 查找匹配的定价
    model_pricing = None
    for key, price in pricing.items():
        if key in model.lower():
            model_pricing = price
            break

    if not model_pricing:
        # 默认使用 GPT-4 定价
        model_pricing = pricing["gpt-4"]

    input_cost = (input_tokens / 1000) * model_pricing["input"]
    output_cost = (output_tokens / 1000) * model_pricing["output"]

    return input_cost + output_cost
