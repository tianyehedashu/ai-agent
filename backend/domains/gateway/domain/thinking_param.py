"""思考模式参数类型推断（与 GatewayModel.tags / 调用指南、Playground 对齐）。"""

from __future__ import annotations

from typing import Any

THINKING_PARAM_NONE = "none"
THINKING_PARAM_DASHSCOPE = "dashscope_enable_thinking"
THINKING_PARAM_BUILTIN = "builtin_reasoning"
THINKING_PARAM_ANTHROPIC = "anthropic_extended"

THINKING_PARAM_VALUES: frozenset[str] = frozenset(
    {
        THINKING_PARAM_NONE,
        THINKING_PARAM_DASHSCOPE,
        THINKING_PARAM_BUILTIN,
        THINKING_PARAM_ANTHROPIC,
    }
)


def _model_id_lower(provider: str, real_model: str) -> str:
    rm = (real_model or "").strip().lower()
    if "/" in rm:
        return rm
    p = (provider or "").strip().lower()
    return f"{p}/{rm}" if p and rm else rm


def infer_thinking_param(
    *,
    provider: str,
    real_model: str,
    supports_reasoning: bool = False,
    explicit: str | None = None,
) -> str:
    """按 provider / real_model 推断思考模式；``explicit`` 为 tags 中显式配置时优先。"""
    if explicit is not None:
        normalized = explicit.strip()
        if normalized in THINKING_PARAM_VALUES:
            return normalized

    combined = _model_id_lower(provider, real_model)
    model_part = combined.split("/")[-1] if combined else ""
    prov = (provider or "").strip().lower()

    if prov == "dashscope":
        if "qwq" in model_part:
            return THINKING_PARAM_BUILTIN
        if "qwen3" in model_part or model_part.startswith("qwen-3"):
            return THINKING_PARAM_DASHSCOPE

    if prov == "deepseek" and "reasoner" in combined:
        return THINKING_PARAM_BUILTIN

    if prov == "anthropic" and supports_reasoning:
        return THINKING_PARAM_ANTHROPIC

    if supports_reasoning:
        return THINKING_PARAM_BUILTIN

    return THINKING_PARAM_NONE


def resolve_thinking_param_from_tags(
    tags: dict[str, Any],
    *,
    provider: str = "",
    real_model: str = "",
) -> str:
    """从 tags 解析 thinking_param；缺失时按 provider/real_model 推断。"""
    explicit = tags.get("thinking_param")
    explicit_str = explicit if isinstance(explicit, str) else None
    supports_reasoning = bool(tags.get("supports_reasoning", False))
    if bool(tags.get("supports_reasoning_content", False)):
        supports_reasoning = True

    prov = str(tags.get("provider") or provider or "")
    rm = str(tags.get("real_model") or real_model or "")
    return infer_thinking_param(
        provider=prov,
        real_model=rm,
        supports_reasoning=supports_reasoning,
        explicit=explicit_str,
    )


def enrich_gateway_model_tags(
    tags: dict[str, Any] | None,
    *,
    provider: str,
    real_model: str,
) -> dict[str, Any]:
    """注册/更新模型时合并 ``thinking_param`` 与 ``supports_reasoning``（权威写入 tags）。"""
    merged: dict[str, Any] = dict(tags or {})
    explicit = merged.get("thinking_param")
    explicit_str = explicit if isinstance(explicit, str) else None
    supports_reasoning = bool(merged.get("supports_reasoning", False))
    if bool(merged.get("supports_reasoning_content", False)):
        supports_reasoning = True

    thinking_param = infer_thinking_param(
        provider=provider,
        real_model=real_model,
        supports_reasoning=supports_reasoning,
        explicit=explicit_str,
    )
    merged["thinking_param"] = thinking_param
    merged["supports_reasoning"] = effective_supports_reasoning(merged, thinking_param)
    return merged


def effective_supports_reasoning(tags: dict[str, Any], thinking_param: str) -> bool:
    """与 thinking_param 对齐的 supports_reasoning（用于目录同步）。"""
    if bool(tags.get("supports_reasoning", False)):
        return True
    if bool(tags.get("supports_reasoning_content", False)):
        return True
    return thinking_param != THINKING_PARAM_NONE


__all__ = [
    "THINKING_PARAM_ANTHROPIC",
    "THINKING_PARAM_BUILTIN",
    "THINKING_PARAM_DASHSCOPE",
    "THINKING_PARAM_NONE",
    "THINKING_PARAM_VALUES",
    "effective_supports_reasoning",
    "enrich_gateway_model_tags",
    "infer_thinking_param",
    "resolve_thinking_param_from_tags",
]
