"""
GatewayPiiGuardrail - LiteLLM CustomGuardrail 适配

脱敏规则见 ``domains.gateway.domain.proxy.pii_redaction_policy``。
"""

from __future__ import annotations

from contextlib import suppress
from typing import Any

from domains.gateway.domain.proxy.pii_redaction_policy import (
    PiiPatterns,
    hash_messages_streaming,
    hash_original,
    redact_messages,
    redact_text,
)


def _import_custom_guardrail() -> Any:
    from litellm.integrations.custom_guardrail import CustomGuardrail

    return CustomGuardrail


class GatewayPiiGuardrail:
    """工厂入口：返回真实 PiiGuardrail 实例（懒加载基类）"""

    def __new__(cls, *args: Any, **kwargs: Any) -> Any:
        return _build_pii_guardrail_instance(*args, **kwargs)


def _build_pii_guardrail_instance(
    guardrail_name: str = "gateway_pii",
    *,
    default_enabled: bool = True,
) -> Any:
    base_cls = _import_custom_guardrail()

    class _Impl(base_cls):  # type: ignore[misc, valid-type]
        def __init__(self) -> None:
            super().__init__(guardrail_name=guardrail_name)
            self.default_enabled = default_enabled

        def _is_enabled(self, data: dict[str, Any]) -> bool:
            metadata = data.get("metadata") or {}
            override = metadata.get("guardrail_enabled")
            if override is None:
                return self.default_enabled
            return bool(override)

        async def async_pre_call_hook(
            self,
            user_api_key_dict: Any,
            cache: Any,
            data: dict[str, Any],
            call_type: str,
        ) -> dict[str, Any] | None:
            if not self._is_enabled(data):
                return None
            messages = data.get("messages")
            if isinstance(messages, list):
                redacted, hits = redact_messages(messages)
                if hits:
                    metadata = data.setdefault("metadata", {})
                    metadata.setdefault("pii_redactions", []).extend(hits)
                    # 流式增量 SHA256，避免一次性拼接 messages 量级临时字符串。
                    # 与 ``hash_original("\n".join(...))`` 输出字节级一致。
                    metadata["pii_prompt_hash"] = hash_messages_streaming(messages)
                    data["messages"] = redacted
            return data

        async def async_moderation_hook(
            self,
            data: dict[str, Any],
            user_api_key_dict: Any,
            call_type: str,
        ) -> Any:
            with suppress(Exception):
                return await self.async_pre_call_hook(user_api_key_dict, None, data, call_type)
            return None

        async def async_dataset_hook(self, *args: Any, **kwargs: Any) -> None:
            return None

    return _Impl()


__all__ = [
    "GatewayPiiGuardrail",
    "PiiPatterns",
    "_build_pii_guardrail_instance",
    "hash_messages_streaming",
    "hash_original",
    "redact_messages",
    "redact_text",
]
