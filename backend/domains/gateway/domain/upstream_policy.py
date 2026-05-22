"""出站前 LiteLLM kwargs 的纯领域策略（无 Session / ORM / LiteLLM）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_PROVIDER_MAX_OUTPUT: dict[str, int] = {
    "deepseek": 65536,
    "dashscope": 8192,
    "zhipuai": 8192,
    "volcengine": 8192,
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
    return "deepseek-reasoner" in combined or (
        "deepseek" in combined and "reasoner" in combined
    )


def preprocess_messages_for_reasoner(
    client_model: str,
    real_model: str,
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not is_deepseek_reasoner(client_model, real_model):
        return messages
    processed: list[dict[str, Any]] = []
    for msg in messages:
        msg_copy = dict(msg)
        if (
            msg_copy.get("role") == "assistant"
            and msg_copy.get("tool_calls")
            and "reasoning_content" not in msg_copy
        ):
            msg_copy["reasoning_content"] = msg_copy.get("content", "") or ""
        processed.append(msg_copy)
    return processed


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
            TEMPERATURE_POLICY_FIXED_1
            if flags.supports_reasoning
            else TEMPERATURE_POLICY_CLIENT
        ),
    )
    return apply_invocation_kwargs(snap, kwargs, validate=False)


__all__ = [
    "UpstreamCapabilityFlags",
    "adapt_kwargs_by_capability",
    "clamp_max_tokens",
    "is_deepseek_reasoner",
    "max_output_tokens_limit",
    "preprocess_messages_for_reasoner",
]
