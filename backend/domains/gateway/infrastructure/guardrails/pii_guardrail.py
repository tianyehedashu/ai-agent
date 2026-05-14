"""
GatewayPiiGuardrail - PII 脱敏 Guardrail

基于 LiteLLM CustomGuardrail，在写日志/出站前对消息做正则脱敏。
默认规则：手机号、邮箱、身份证、银行卡、IP。

vkey 可单独关闭：通过 LiteLLM 调用 metadata 传入 `guardrail_enabled=False`
（由 ProxyUseCase 注入），命中时跳过脱敏。

注意：此 guardrail 默认不阻断请求（不抛异常），只把命中位置替换为占位符
并把原文 hash 写入日志元数据。如果团队希望"命中即阻断"，可在 vkey 设置中
开启严格模式（待续）。
"""

from __future__ import annotations

from contextlib import suppress
import hashlib
import re
from typing import Any, ClassVar


class PiiPatterns:
    """常见 PII 正则"""

    # 中国大陆手机号
    PHONE = re.compile(r"(?<![0-9])1[3-9]\d{9}(?![0-9])")
    # 邮箱
    EMAIL = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
    # 中国大陆身份证（18 位，含校验位规则放宽）
    ID_CARD = re.compile(
        r"(?<![0-9Xx])(\d{6}(?:18|19|20)\d{2}(?:0[1-9]|1[0-2])"
        r"(?:0[1-9]|[12]\d|3[01])\d{3}[0-9Xx])(?![0-9Xx])"
    )
    # 银行卡 13-19 位连续数字
    BANK_CARD = re.compile(r"(?<![0-9])\d{13,19}(?![0-9])")
    # IPv4
    IPV4 = re.compile(r"(?<![0-9.])\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?![0-9.])")

    REDACTIONS: ClassVar[list[tuple[re.Pattern[str], str]]] = [
        (PHONE, "[REDACTED_PHONE]"),
        (EMAIL, "[REDACTED_EMAIL]"),
        (ID_CARD, "[REDACTED_ID]"),
        (BANK_CARD, "[REDACTED_CARD]"),
        (IPV4, "[REDACTED_IP]"),
    ]


def redact_text(text: str) -> tuple[str, list[str]]:
    """对单段文本脱敏

    Returns:
        (redacted_text, hit_categories) - 脱敏后的文本与命中类别（去重）
    """
    if not text:
        return text, []
    hits: list[str] = []
    redacted = text
    for pattern, placeholder in PiiPatterns.REDACTIONS:
        if pattern.search(redacted):
            hits.append(placeholder.strip("[]").lower())
            redacted = pattern.sub(placeholder, redacted)
    # 去重保序
    seen: set[str] = set()
    unique_hits: list[str] = []
    for h in hits:
        if h not in seen:
            seen.add(h)
            unique_hits.append(h)
    return redacted, unique_hits


def hash_original(text: str) -> str:
    """对原文做 sha256，便于在日志中关联但不存原文"""
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def redact_messages(messages: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    """对一组 OpenAI 兼容消息做脱敏，返回脱敏副本与命中类别"""
    all_hits: set[str] = set()
    out: list[dict[str, Any]] = []
    for msg in messages:
        new_msg = dict(msg)
        content = msg.get("content")
        if isinstance(content, str):
            redacted, hits = redact_text(content)
            new_msg["content"] = redacted
            all_hits.update(hits)
        elif isinstance(content, list):
            new_parts: list[Any] = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    text = part.get("text", "")
                    redacted, hits = redact_text(text)
                    new_part = dict(part)
                    new_part["text"] = redacted
                    new_parts.append(new_part)
                    all_hits.update(hits)
                else:
                    new_parts.append(part)
            new_msg["content"] = new_parts
        out.append(new_msg)
    return out, sorted(all_hits)


# =============================================================================
# LiteLLM CustomGuardrail
# =============================================================================


def _import_custom_guardrail() -> Any:
    """延迟导入避免顶层依赖 litellm"""
    from litellm.integrations.custom_guardrail import CustomGuardrail

    return CustomGuardrail


class GatewayPiiGuardrail:  # 在初始化时返回真正继承 CustomGuardrail 的实例
    """工厂入口：返回真实 PiiGuardrail 实例（懒加载基类）"""

    def __new__(cls, *args: Any, **kwargs: Any) -> Any:
        return _build_pii_guardrail_instance(*args, **kwargs)


def _build_pii_guardrail_instance(
    guardrail_name: str = "gateway_pii",
    *,
    default_enabled: bool = True,
) -> Any:
    """动态创建继承 CustomGuardrail 的 PII Guardrail 实例

    返回的对象可作为 callback 注册到 litellm.callbacks。
    """
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
                    metadata["pii_prompt_hash"] = hash_original(
                        "\n".join(
                            str(m.get("content", ""))
                            for m in messages
                            if isinstance(m.get("content"), str)
                        )
                    )
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
            """LiteLLM 基类抽象钩子；Gateway Guardrail 不使用 dataset。"""
            return None

    return _Impl()


__all__ = [
    "GatewayPiiGuardrail",
    "PiiPatterns",
    "_build_pii_guardrail_instance",
    "hash_original",
    "redact_messages",
    "redact_text",
]
