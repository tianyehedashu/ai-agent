"""Anthropic Messages 协议私有字段剥离策略（纯函数 + 原地剥离）。

Claude Code / Anthropic SDK 走 ``POST /v1/messages`` 时，请求体可能携带 Anthropic
私有字段。非 Anthropic 上游默认剥离；``thinking`` 由 ``invocation_policy`` 按模型
``thinking_param`` 处理，不在此清单。

运营可通过 ``GatewayModel.tags`` 覆盖默认剥离行为（见 ``resolve_fields_to_strip``）。
详细分层说明见 ``docs/gateway/LITELLM_CAPABILITY_MATRIX.md`` §跨协议字段剥离策略。
"""

from __future__ import annotations

from typing import Any

ANTHROPIC_UPSTREAM_PROVIDER = "anthropic"

# tags["anthropic_messages_field_policy"]：模型级覆盖 provider 默认剥离。
ANTHROPIC_MESSAGES_FIELD_POLICY_TAG = "anthropic_messages_field_policy"
ANTHROPIC_MESSAGES_FIELD_POLICY_NATIVE = "native"
ANTHROPIC_MESSAGES_FIELD_POLICY_STRIP = "strip"
ANTHROPIC_MESSAGES_FIELD_POLICY_VALUES: frozenset[str] = frozenset(
    {
        ANTHROPIC_MESSAGES_FIELD_POLICY_NATIVE,
        ANTHROPIC_MESSAGES_FIELD_POLICY_STRIP,
    }
)

# tags["preserve_anthropic_fields"]：非 Anthropic 上游仍保留清单内指定字段（字段级例外）。
PRESERVE_ANTHROPIC_FIELDS_TAG = "preserve_anthropic_fields"

# Anthropic Messages 协议私有且无跨 provider 翻译能力的请求字段（不含 ``thinking``）。
# 固定顺序供 ``resolve_fields_to_strip`` / ``find_anthropic_only_fields_present`` 稳定枚举。
_ANTHROPIC_ONLY_REQUEST_FIELD_ORDER: tuple[str, ...] = (
    "context_management",
    "anthropic_version",
    "anthropic_beta",
)
ANTHROPIC_ONLY_REQUEST_FIELDS: frozenset[str] = frozenset(_ANTHROPIC_ONLY_REQUEST_FIELD_ORDER)


def normalize_upstream_provider(upstream_provider: str | None) -> str:
    """规范化 ``GatewayModel.provider``（小写、去空白）。"""
    return (upstream_provider or "").strip().lower()


def is_anthropic_upstream(upstream_provider: str | None) -> bool:
    """目标上游是否为 Anthropic 原生（保留 Anthropic 私有字段）。"""
    return normalize_upstream_provider(upstream_provider) == ANTHROPIC_UPSTREAM_PROVIDER


def should_strip_for_upstream(upstream_provider: str | None) -> bool:
    """是否应针对该上游考虑剥离 Anthropic-only 字段（不含 tags 例外）。

    - ``"anthropic"`` → 不剥离；
    - 已知非 Anthropic provider → 可剥离（再经 ``model_tags`` 收窄）；
    - ``None`` / 空串 → **不剥离**，交由 ``litellm.drop_params`` 兜底。
    """
    cleaned = normalize_upstream_provider(upstream_provider)
    if not cleaned:
        return False
    return cleaned != ANTHROPIC_UPSTREAM_PROVIDER


def _field_policy_from_tags(model_tags: dict[str, Any] | None) -> str | None:
    if model_tags is None:
        return None
    raw = model_tags.get(ANTHROPIC_MESSAGES_FIELD_POLICY_TAG)
    if not isinstance(raw, str):
        return None
    normalized = raw.strip().lower()
    if normalized in ANTHROPIC_MESSAGES_FIELD_POLICY_VALUES:
        return normalized
    return None


def _preserve_fields_from_tags(model_tags: dict[str, Any] | None) -> frozenset[str]:
    if model_tags is None:
        return frozenset()
    raw = model_tags.get(PRESERVE_ANTHROPIC_FIELDS_TAG)
    if not isinstance(raw, (list, tuple, frozenset, set)):
        return frozenset()
    preserved: set[str] = set()
    for item in raw:
        if not isinstance(item, str):
            continue
        key = item.strip()
        if key in ANTHROPIC_ONLY_REQUEST_FIELDS:
            preserved.add(key)
    return frozenset(preserved)


def resolve_fields_to_strip(
    kwargs: dict[str, Any],
    *,
    upstream_provider: str | None,
    model_tags: dict[str, Any] | None = None,
) -> list[str]:
    """按 provider + 模型 tags 解析应剥离的 Anthropic-only 字段名（纯查询）。

    决策顺序：
    1. Anthropic 上游 / provider 未知 → 空；
    2. ``tags["anthropic_messages_field_policy"] == "native"`` → 空（全量透传）；
    3. 默认剥离清单内字段，减去 ``tags["preserve_anthropic_fields"]`` 例外。
    """
    if not should_strip_for_upstream(upstream_provider):
        return []
    if _field_policy_from_tags(model_tags) == ANTHROPIC_MESSAGES_FIELD_POLICY_NATIVE:
        return []
    preserve = _preserve_fields_from_tags(model_tags)
    return [
        key for key in _ANTHROPIC_ONLY_REQUEST_FIELD_ORDER if key in kwargs and key not in preserve
    ]


def find_anthropic_only_fields_present(kwargs: dict[str, Any]) -> list[str]:
    """枚举 kwargs 中出现的 Anthropic-only 字段名（纯查询，按清单顺序）。"""
    return [key for key in _ANTHROPIC_ONLY_REQUEST_FIELD_ORDER if key in kwargs]


def strip_anthropic_only_fields(
    kwargs: dict[str, Any],
    *,
    upstream_provider: str | None,
    model_tags: dict[str, Any] | None = None,
) -> list[str]:
    """**原地**剥离 Anthropic-only 请求字段，返回实际被剥离的字段名列表。"""
    dropped = resolve_fields_to_strip(
        kwargs,
        upstream_provider=upstream_provider,
        model_tags=model_tags,
    )
    for key in dropped:
        kwargs.pop(key, None)
    return dropped


__all__ = [
    "ANTHROPIC_MESSAGES_FIELD_POLICY_NATIVE",
    "ANTHROPIC_MESSAGES_FIELD_POLICY_STRIP",
    "ANTHROPIC_MESSAGES_FIELD_POLICY_TAG",
    "ANTHROPIC_MESSAGES_FIELD_POLICY_VALUES",
    "ANTHROPIC_ONLY_REQUEST_FIELDS",
    "ANTHROPIC_UPSTREAM_PROVIDER",
    "PRESERVE_ANTHROPIC_FIELDS_TAG",
    "find_anthropic_only_fields_present",
    "is_anthropic_upstream",
    "normalize_upstream_provider",
    "resolve_fields_to_strip",
    "should_strip_for_upstream",
    "strip_anthropic_only_fields",
]
