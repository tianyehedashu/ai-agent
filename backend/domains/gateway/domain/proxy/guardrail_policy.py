"""Gateway PII Guardrail 开关策略（纯函数）。"""

from __future__ import annotations

from libs.exceptions import ValidationError


def effective_guardrail_enabled(
    *,
    global_guardrail_enabled: bool,
    vkey_guardrail_enabled: bool,
) -> bool:
    """单次代理是否应对 messages 做 PII 脱敏。"""
    return global_guardrail_enabled and vkey_guardrail_enabled


def assert_vkey_guardrail_create_allowed(
    *,
    global_guardrail_enabled: bool,
    requested_guardrail_enabled: bool,
) -> None:
    """创建虚拟 Key 时：全局未开放则禁止请求启用 PII 守卫。"""
    if requested_guardrail_enabled and not global_guardrail_enabled:
        raise ValidationError(
            "PII 守卫尚未开放，请保持 guardrail_enabled=false；"
            "部署侧需设置 GATEWAY_DEFAULT_GUARDRAIL_ENABLED=true 后方可启用"
        )


__all__ = [
    "assert_vkey_guardrail_create_allowed",
    "effective_guardrail_enabled",
]
