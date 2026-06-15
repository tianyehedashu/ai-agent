"""温度出站策略（与 ``GatewayModel.tags`` / ``ModelCapabilitySnapshot`` 对齐）。"""

from __future__ import annotations

from typing import Any

# 与 thinking_param.THINKING_PARAM_NONE 同值；勿从 thinking_param 导入（会与 enrich_temperature_tags 形成环）。
_THINKING_PARAM_NONE = "none"

TEMPERATURE_POLICY_CLIENT = "client"
TEMPERATURE_POLICY_FIXED_1 = "fixed_1"
TEMPERATURE_POLICY_PROBE_0 = "probe_0"

TEMPERATURE_POLICY_VALUES: frozenset[str] = frozenset(
    {
        TEMPERATURE_POLICY_CLIENT,
        TEMPERATURE_POLICY_FIXED_1,
        TEMPERATURE_POLICY_PROBE_0,
    }
)

DEFAULT_CLIENT_TEMPERATURE = 0.7
TEMPERATURE_MIN = 0.0
TEMPERATURE_MAX = 2.0

# Moonshot Kimi Code（``moonshot.coding_plan``）：上游仅接受 temperature=1
_FIXED_TEMPERATURE_1_MODEL_IDS: frozenset[str] = frozenset(
    {
        "kimi-for-coding",
        "kimi-for-coding-chat",
    }
)


def requires_fixed_temperature_1(*, real_model: str = "") -> bool:
    """上游硬性要求 ``temperature=1`` 的模型（与思考模式 / tags 显式 client 无关）。"""
    rm = (real_model or "").strip().lower()
    if not rm:
        return False
    model_part = rm.split("/")[-1]
    return model_part in _FIXED_TEMPERATURE_1_MODEL_IDS


def infer_temperature_policy(
    *,
    thinking_param: str,
    supports_reasoning: bool = False,
    explicit: str | None = None,
    real_model: str = "",
) -> str:
    """推断温度策略；``explicit`` 为 tags 显式配置时优先（Coding 模型硬约束除外）。"""
    if requires_fixed_temperature_1(real_model=real_model):
        return TEMPERATURE_POLICY_FIXED_1

    if explicit is not None:
        normalized = explicit.strip()
        if normalized in TEMPERATURE_POLICY_VALUES:
            return normalized

    if thinking_param != _THINKING_PARAM_NONE or supports_reasoning:
        return TEMPERATURE_POLICY_FIXED_1
    return TEMPERATURE_POLICY_CLIENT


def resolve_temperature_policy_from_tags(
    tags: dict[str, Any],
    *,
    thinking_param: str,
    real_model: str = "",
) -> str:
    """从 tags 解析 ``temperature_policy``。"""
    explicit = tags.get("temperature_policy")
    explicit_str = explicit if isinstance(explicit, str) else None
    supports_reasoning = bool(tags.get("supports_reasoning", False))
    if bool(tags.get("supports_reasoning_content", False)):
        supports_reasoning = True
    rm = str(tags.get("real_model") or real_model or "")
    return infer_temperature_policy(
        thinking_param=thinking_param,
        supports_reasoning=supports_reasoning,
        explicit=explicit_str,
        real_model=rm,
    )


def resolve_temperature_default_from_tags(tags: dict[str, Any]) -> float:
    """解析可选默认温度（仅 ``client`` 策略使用）。"""
    raw = tags.get("temperature_default")
    if isinstance(raw, (int, float)):
        value = float(raw)
        if TEMPERATURE_MIN <= value <= TEMPERATURE_MAX:
            return value
    return DEFAULT_CLIENT_TEMPERATURE


def enrich_temperature_tags(
    tags: dict[str, Any],
    *,
    thinking_param: str,
) -> dict[str, Any]:
    """合并 ``temperature_policy`` / ``temperature_default`` 到 tags。"""
    merged = dict(tags)
    policy = resolve_temperature_policy_from_tags(
        merged,
        thinking_param=thinking_param,
        real_model=str(merged.get("real_model") or ""),
    )
    merged["temperature_policy"] = policy
    if policy == TEMPERATURE_POLICY_CLIENT:
        merged["temperature_default"] = resolve_temperature_default_from_tags(merged)
    return merged


__all__ = [
    "DEFAULT_CLIENT_TEMPERATURE",
    "TEMPERATURE_MAX",
    "TEMPERATURE_MIN",
    "TEMPERATURE_POLICY_CLIENT",
    "TEMPERATURE_POLICY_FIXED_1",
    "TEMPERATURE_POLICY_PROBE_0",
    "TEMPERATURE_POLICY_VALUES",
    "enrich_temperature_tags",
    "infer_temperature_policy",
    "requires_fixed_temperature_1",
    "resolve_temperature_default_from_tags",
    "resolve_temperature_policy_from_tags",
]
