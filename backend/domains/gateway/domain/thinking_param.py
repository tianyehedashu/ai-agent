"""思考模式参数类型推断（与 GatewayModel.tags / 调用指南、Playground 对齐）。"""

from __future__ import annotations

from typing import Any

from domains.gateway.domain.temperature_policy import enrich_temperature_tags

THINKING_PARAM_NONE = "none"
THINKING_PARAM_DASHSCOPE = "dashscope_enable_thinking"
THINKING_PARAM_BUILTIN = "builtin_reasoning"
THINKING_PARAM_ANTHROPIC = "anthropic_extended"
THINKING_PARAM_DEEPSEEK_V4 = "deepseek_v4_thinking"

# 运营显式写入 thinking_param=none 时置 true，阻止按 real_model 重新推断（GatewayModel.tags）。
THINKING_PARAM_LOCKED_TAG = "thinking_param_locked"

THINKING_PARAM_VALUES: frozenset[str] = frozenset(
    {
        THINKING_PARAM_NONE,
        THINKING_PARAM_DASHSCOPE,
        THINKING_PARAM_BUILTIN,
        THINKING_PARAM_ANTHROPIC,
        THINKING_PARAM_DEEPSEEK_V4,
    }
)


def is_deepseek_v4_model_id(model_id: str) -> bool:
    """DeepSeek V4 Pro/Flash：OpenAI 兼容入口 + ``extra_body.thinking`` 可开关。

    前端 ``model-selector-capabilities`` 的弱推断须与此规则保持同步。
    """
    lower = (model_id or "").strip().lower()
    if not lower:
        return False
    model_part = lower.split("/")[-1]
    return "deepseek-v4-pro" in model_part or "deepseek-v4-flash" in model_part


def _model_id_lower(provider: str, real_model: str) -> str:
    rm = (real_model or "").strip().lower()
    if "/" in rm:
        return rm
    p = (provider or "").strip().lower()
    return f"{p}/{rm}" if p and rm else rm


def _normalized_thinking_param(raw: object) -> str | None:
    if not isinstance(raw, str):
        return None
    normalized = raw.strip()
    return normalized if normalized in THINKING_PARAM_VALUES else None


def _thinking_param_locked(tags: dict[str, Any]) -> bool:
    return tags.get(THINKING_PARAM_LOCKED_TAG) is True


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

    if is_deepseek_v4_model_id(combined) or is_deepseek_v4_model_id(model_part):
        return THINKING_PARAM_DEEPSEEK_V4

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
    """从 tags 解析 thinking_param；读写路径 SSOT（enrich 与出站快照共用）。"""
    explicit = _normalized_thinking_param(tags.get("thinking_param"))
    supports_reasoning = bool(tags.get("supports_reasoning", False))
    if bool(tags.get("supports_reasoning_content", False)):
        supports_reasoning = True

    prov = str(tags.get("provider") or provider or "")
    rm = str(tags.get("real_model") or real_model or "")
    inferred = infer_thinking_param(
        provider=prov,
        real_model=rm,
        supports_reasoning=supports_reasoning,
        explicit=None,
    )

    if explicit is not None and explicit != THINKING_PARAM_NONE:
        return explicit
    if explicit == THINKING_PARAM_NONE and _thinking_param_locked(tags):
        return THINKING_PARAM_NONE
    return inferred


def enrich_gateway_model_tags(
    tags: dict[str, Any] | None,
    *,
    provider: str,
    real_model: str,
) -> dict[str, Any]:
    """注册/更新模型时合并 ``thinking_param`` 与 ``supports_reasoning``（权威写入 tags）。"""
    merged: dict[str, Any] = dict(tags or {})
    merged["provider"] = provider
    merged["real_model"] = real_model

    thinking_param = resolve_thinking_param_from_tags(
        merged, provider=provider, real_model=real_model
    )
    merged["thinking_param"] = thinking_param
    merged["supports_reasoning"] = effective_supports_reasoning(merged, thinking_param)
    return enrich_temperature_tags(merged, thinking_param=thinking_param)


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
    "THINKING_PARAM_DEEPSEEK_V4",
    "THINKING_PARAM_LOCKED_TAG",
    "THINKING_PARAM_NONE",
    "THINKING_PARAM_VALUES",
    "effective_supports_reasoning",
    "enrich_gateway_model_tags",
    "infer_thinking_param",
    "is_deepseek_v4_model_id",
    "resolve_thinking_param_from_tags",
]
