"""跨域调用覆盖：将 ``InvocationOverrides`` 合并进 OpenAI 形 body。"""

from __future__ import annotations

from typing import Any

from domains.gateway.application.ports import InvocationOverrides
from domains.gateway.domain.model_capability import ModelCapabilitySnapshot
from domains.gateway.domain.policies.invocation_policy import (
    client_thinking_request_fields,
    validate_client_thinking_toggle,
)


def merge_invocation_overrides_into_body(
    body: dict[str, Any],
    overrides: InvocationOverrides | None,
    *,
    capabilities: ModelCapabilitySnapshot | None = None,
) -> None:
    """就地合并温度与思考覆盖（由 ``GatewayBridge`` 在出站前调用）。"""
    if overrides is None:
        return
    if overrides.temperature is not None:
        body["temperature"] = overrides.temperature
    if overrides.thinking_enabled is None:
        return
    validate_client_thinking_toggle(capabilities, enabled=overrides.thinking_enabled)
    if capabilities is None:
        return
    for key, val in client_thinking_request_fields(
        capabilities, enabled=overrides.thinking_enabled
    ).items():
        if key == "extra_body" and isinstance(val, dict):
            existing = body.get("extra_body")
            merged_extra = dict(existing) if isinstance(existing, dict) else {}
            merged_extra.update(val)
            body["extra_body"] = merged_extra
        else:
            body[key] = val


__all__ = ["merge_invocation_overrides_into_body"]
