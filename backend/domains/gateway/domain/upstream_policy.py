"""出站前 LiteLLM kwargs 的纯领域策略（无 Session / ORM / LiteLLM）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from domains.gateway.domain.thinking_param import is_deepseek_v4_model_id

_PROVIDER_MAX_OUTPUT: dict[str, int] = {
    "deepseek": 65536,
    "dashscope": 8192,
    "zhipuai": 8192,
    "volcengine": 8192,
    "moonshot": 8192,
    "openai": 4096,
    "anthropic": 4096,
}


@dataclass(frozen=True)
class UpstreamCapabilityFlags:
    supports_tools: bool = True
    supports_reasoning: bool = False
    supports_json_mode: bool = True


def is_deepseek_reasoner(client_model: str, real_model: str) -> bool:
    combined = f"{real_model} {client_model}".lower()
    return "deepseek-reasoner" in combined or ("deepseek" in combined and "reasoner" in combined)


def is_deepseek_thinking_model(client_model: str, real_model: str) -> bool:
    """DeepSeek reasoner 或 V4 Pro/Flash：tool call 多轮须回传 reasoning_content。"""
    combined = f"{real_model} {client_model}".lower()
    if is_deepseek_reasoner(client_model, real_model):
        return True
    return is_deepseek_v4_model_id(combined)


def _text_from_content(content: Any) -> str:
    """从 ``content``（str 或 content-parts list）提取纯文本。"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts: list[str] = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                texts.append(str(part.get("text", "")))
        return "".join(texts)
    return ""


def preprocess_messages_for_reasoner(
    client_model: str,
    real_model: str,
    messages: list[dict[str, Any]],
    *,
    supports_reasoning: bool = False,
) -> list[dict[str, Any]]:
    """为 thinking 模型回填缺失的 ``reasoning_content``。

    当 ``supports_reasoning=True``（来自 ``ModelCapabilitySnapshot``）时，对所有
    thinking 模型生效（Moonshot/Kimi、DeepSeek 等）；否则回退到 DeepSeek 遗留检测。
    """
    if not supports_reasoning and not is_deepseek_thinking_model(client_model, real_model):
        return messages
    processed: list[dict[str, Any]] = []
    for msg in messages:
        msg_copy = dict(msg)
        if (
            msg_copy.get("role") == "assistant"
            and msg_copy.get("tool_calls")
            and "reasoning_content" not in msg_copy
        ):
            msg_copy["reasoning_content"] = _text_from_content(msg_copy.get("content")) or ""
        processed.append(msg_copy)
    return processed


def flatten_text_only_content_arrays(
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """将仅含 text 类型的 content array 降级为字符串。

    用于不支持 OpenAI content parts 数组的上游（如 Deepseek）。
    若包含非 text 部分（如 image_url），保留原样，由上游返回明确错误。
    """
    for msg in messages:
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        texts: list[str] = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                texts.append(part.get("text", ""))
            else:
                break
        else:
            msg["content"] = "".join(texts)
    return messages


def max_output_tokens_limit(tags: dict[str, Any], provider: str) -> int:
    raw = tags.get("context_window")
    if isinstance(raw, int) and raw > 0:
        return min(raw, _PROVIDER_MAX_OUTPUT.get(provider, 4096))
    return _PROVIDER_MAX_OUTPUT.get(provider, 4096)


def clamp_max_tokens(kwargs: dict[str, Any], limit: int) -> dict[str, Any]:
    """返回可能调整过 ``max_tokens`` 的 kwargs 副本。"""
    adapted = dict(kwargs)
    raw = adapted.get("max_tokens")
    if raw is None:
        return adapted
    try:
        max_tokens = int(raw)
    except (TypeError, ValueError):
        return adapted
    if max_tokens > limit:
        adapted["max_tokens"] = limit
    elif max_tokens < 1:
        adapted["max_tokens"] = 1
    return adapted


def adapt_kwargs_by_capability(
    kwargs: dict[str, Any],
    flags: UpstreamCapabilityFlags,
) -> dict[str, Any]:
    """已废弃：请改用 ``apply_invocation_kwargs`` + ``ModelCapabilitySnapshot``。

    计划在后续版本移除本包装；新代码勿再调用。
    """
    from domains.gateway.domain.model_capability import ModelCapabilitySnapshot
    from domains.gateway.domain.policies.invocation_policy import apply_invocation_kwargs
    from domains.gateway.domain.temperature_policy import (
        TEMPERATURE_POLICY_CLIENT,
        TEMPERATURE_POLICY_FIXED_1,
    )

    snap = ModelCapabilitySnapshot(
        supports_tools=flags.supports_tools,
        supports_reasoning=flags.supports_reasoning,
        supports_json_mode=flags.supports_json_mode,
        temperature_policy=(
            TEMPERATURE_POLICY_FIXED_1 if flags.supports_reasoning else TEMPERATURE_POLICY_CLIENT
        ),
    )
    return apply_invocation_kwargs(snap, kwargs, validate=False)


__all__ = [
    "UpstreamCapabilityFlags",
    "_text_from_content",
    "adapt_kwargs_by_capability",
    "clamp_max_tokens",
    "flatten_text_only_content_arrays",
    "is_deepseek_reasoner",
    "is_deepseek_thinking_model",
    "max_output_tokens_limit",
    "preprocess_messages_for_reasoner",
]
