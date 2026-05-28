"""出站 kwargs 调用策略（思考模式 + 温度 + tools/json；纯领域，无 I/O）。"""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

from domains.gateway.domain.errors import InvocationPolicyViolationError
from domains.gateway.domain.temperature_policy import (
    TEMPERATURE_MAX,
    TEMPERATURE_MIN,
    TEMPERATURE_POLICY_CLIENT,
    TEMPERATURE_POLICY_FIXED_1,
    TEMPERATURE_POLICY_PROBE_0,
)
from domains.gateway.domain.thinking_param import (
    THINKING_PARAM_ANTHROPIC,
    THINKING_PARAM_BUILTIN,
    THINKING_PARAM_DASHSCOPE,
    THINKING_PARAM_DEEPSEEK_V4,
    THINKING_PARAM_NONE,
)

if TYPE_CHECKING:
    from domains.gateway.domain.model_capability import ModelCapabilitySnapshot


def _extra_body_dict(kwargs: dict[str, Any]) -> dict[str, Any] | None:
    raw = kwargs.get("extra_body")
    return raw if isinstance(raw, dict) else None


def _enable_thinking_requested(kwargs: dict[str, Any]) -> bool:
    if kwargs.get("enable_thinking") is True:
        return True
    extra = _extra_body_dict(kwargs)
    return extra is not None and extra.get("enable_thinking") is True


def _strip_enable_thinking(adapted: dict[str, Any]) -> None:
    adapted.pop("enable_thinking", None)
    extra = _extra_body_dict(adapted)
    if extra is not None and "enable_thinking" in extra:
        new_extra = dict(extra)
        new_extra.pop("enable_thinking", None)
        if new_extra:
            adapted["extra_body"] = new_extra
        else:
            adapted.pop("extra_body", None)


def _strip_thinking_block(adapted: dict[str, Any]) -> None:
    adapted.pop("thinking", None)


def _extra_body_thinking_type(kwargs: dict[str, Any]) -> str | None:
    extra = _extra_body_dict(kwargs)
    if extra is None:
        return None
    thinking = extra.get("thinking")
    if not isinstance(thinking, dict):
        return None
    raw = thinking.get("type")
    return raw if isinstance(raw, str) else None


def _top_level_thinking_type(kwargs: dict[str, Any]) -> str | None:
    raw = kwargs.get("thinking")
    if not isinstance(raw, dict):
        return None
    top_type = raw.get("type")
    return top_type if isinstance(top_type, str) else None


def _translate_anthropic_thinking_to_extra_body(adapted: dict[str, Any]) -> None:
    """Claude Code ``POST /v1/messages`` 顶层 thinking → ``extra_body.thinking``（DeepSeek V4）。"""
    top_type = _top_level_thinking_type(adapted)
    if top_type not in ("enabled", "disabled"):
        return
    extra = dict(_extra_body_dict(adapted) or {})
    if "thinking" in extra:
        return
    extra["thinking"] = {"type": top_type}
    adapted["extra_body"] = extra


def _apply_deepseek_v4_thinking(adapted: dict[str, Any]) -> None:
    _translate_anthropic_thinking_to_extra_body(adapted)
    _strip_thinking_block(adapted)
    if _extra_body_thinking_type(adapted) not in ("enabled", "disabled"):
        _strip_extra_body_thinking(adapted)


def _strip_extra_body_thinking(adapted: dict[str, Any]) -> None:
    extra = _extra_body_dict(adapted)
    if extra is None or "thinking" not in extra:
        return
    new_extra = dict(extra)
    new_extra.pop("thinking", None)
    if new_extra:
        adapted["extra_body"] = new_extra
    else:
        adapted.pop("extra_body", None)


def validate_invocation_kwargs(
    snap: ModelCapabilitySnapshot,
    kwargs: dict[str, Any],
) -> None:
    """校验思考相关组合；违规抛 ``InvocationPolicyViolationError``。

    ``thinking_param=none`` 时不在此拒绝 ``thinking`` / ``enable_thinking``：
    由 ``_apply_thinking_kwargs`` 静默剥离（兼容 Claude Code 等默认携带 Extended Thinking
    的客户端）。显式开启思考仍走 ``validate_client_thinking_toggle``。
    """
    if snap.thinking_param == THINKING_PARAM_NONE:
        return

    if snap.thinking_param == THINKING_PARAM_DASHSCOPE:
        if not _enable_thinking_requested(kwargs):
            return
        stream = kwargs.get("stream")
        if stream is True:
            return
        extra = _extra_body_dict(kwargs)
        if kwargs.get("enable_thinking") is False:
            return
        if extra is not None and extra.get("enable_thinking") is False:
            return
        raise InvocationPolicyViolationError(
            "DashScope Qwen3 开启思考模式须 stream: true，"
            "或非流式请求显式设置 enable_thinking: false"
        )


def _apply_thinking_kwargs(adapted: dict[str, Any], snap: ModelCapabilitySnapshot) -> None:
    if snap.thinking_param == THINKING_PARAM_NONE:
        _strip_enable_thinking(adapted)
        _strip_thinking_block(adapted)
        _strip_extra_body_thinking(adapted)
        return

    if snap.thinking_param in (
        THINKING_PARAM_BUILTIN,
        THINKING_PARAM_ANTHROPIC,
        THINKING_PARAM_DEEPSEEK_V4,
    ):
        _strip_enable_thinking(adapted)

    if snap.thinking_param == THINKING_PARAM_DASHSCOPE:
        if not _enable_thinking_requested(adapted):
            _strip_enable_thinking(adapted)
        return

    if snap.thinking_param == THINKING_PARAM_ANTHROPIC:
        return

    if snap.thinking_param == THINKING_PARAM_DEEPSEEK_V4:
        _apply_deepseek_v4_thinking(adapted)
        return

    if snap.thinking_param == THINKING_PARAM_BUILTIN:
        _strip_thinking_block(adapted)
        _strip_extra_body_thinking(adapted)


def _clamp_temperature_value(value: float) -> float:
    return max(TEMPERATURE_MIN, min(TEMPERATURE_MAX, value))


def _apply_temperature_kwargs(adapted: dict[str, Any], snap: ModelCapabilitySnapshot) -> None:
    policy = snap.temperature_policy
    if policy == TEMPERATURE_POLICY_FIXED_1:
        adapted["temperature"] = 1.0
        return
    if policy == TEMPERATURE_POLICY_PROBE_0:
        adapted["temperature"] = 0.0
        return
    if policy == TEMPERATURE_POLICY_CLIENT:
        raw = adapted.get("temperature")
        if raw is None:
            adapted["temperature"] = snap.temperature_default
            return
        try:
            temp = float(raw)
        except (TypeError, ValueError) as exc:
            raise InvocationPolicyViolationError(f"temperature 须为数字，收到: {raw!r}") from exc
        adapted["temperature"] = _clamp_temperature_value(temp)
        return
    adapted["temperature"] = snap.temperature_default


def _apply_capability_strips(adapted: dict[str, Any], snap: ModelCapabilitySnapshot) -> None:
    if (
        snap.supports_reasoning
        or snap.thinking_param != THINKING_PARAM_NONE
        or not snap.supports_json_mode
    ):
        adapted.pop("response_format", None)
    if not snap.supports_tools:
        adapted.pop("tools", None)
        adapted.pop("tool_choice", None)


def validate_client_thinking_toggle(
    snap: ModelCapabilitySnapshot | None,
    *,
    enabled: bool | None,
) -> None:
    """客户端显式开启思考时校验模型能力已解析且支持。"""
    if enabled is not True:
        return
    if snap is None:
        raise InvocationPolicyViolationError(
            "无法解析模型能力，无法开启思考模式；请确认 model 已注册且 enabled"
        )
    if snap.thinking_param == THINKING_PARAM_NONE:
        raise InvocationPolicyViolationError("当前模型不支持思考模式，请勿设置 thinking_enabled")


def client_thinking_request_fields(
    snap: ModelCapabilitySnapshot,
    *,
    enabled: bool,
) -> dict[str, Any]:
    """按 ``thinking_param`` 生成客户端思考开关片段（OpenAI 形 body）。"""
    if not enabled:
        if snap.thinking_param == THINKING_PARAM_DASHSCOPE:
            return {"enable_thinking": False, "extra_body": {"enable_thinking": False}}
        if snap.thinking_param == THINKING_PARAM_DEEPSEEK_V4:
            return {"extra_body": {"thinking": {"type": "disabled"}}}
        return {}

    if snap.thinking_param == THINKING_PARAM_DASHSCOPE:
        return {
            "stream": True,
            "enable_thinking": True,
            "extra_body": {"enable_thinking": True},
        }
    if snap.thinking_param == THINKING_PARAM_ANTHROPIC:
        return {"thinking": {"type": "enabled", "budget_tokens": 8000}}
    if snap.thinking_param == THINKING_PARAM_DEEPSEEK_V4:
        return {"extra_body": {"thinking": {"type": "enabled"}}}
    return {}


def apply_invocation_kwargs(
    snap: ModelCapabilitySnapshot,
    kwargs: dict[str, Any],
    *,
    validate: bool = True,
) -> dict[str, Any]:
    """校验并改写出站 kwargs（返回副本）。"""
    if validate:
        validate_invocation_kwargs(snap, kwargs)
    adapted = copy.deepcopy(kwargs)
    _apply_capability_strips(adapted, snap)
    _apply_thinking_kwargs(adapted, snap)
    _apply_temperature_kwargs(adapted, snap)
    return adapted


__all__ = [
    "apply_invocation_kwargs",
    "client_thinking_request_fields",
    "validate_client_thinking_toggle",
    "validate_invocation_kwargs",
]
