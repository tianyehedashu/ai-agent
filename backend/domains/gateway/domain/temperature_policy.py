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

# 注册模型 tags 中 denormalize 的凭据 profile（与 ``gateway_credential_profile_id`` 同 id 空间）
UPSTREAM_PROFILE_ID_TAG = "upstream_profile_id"


def temperature_policy_from_upstream_profile(
    *,
    credential_profile_id: str | None,
    provider: str,
) -> str | None:
    """按 ``UpstreamProfile.fixed_outbound_temperature`` 解析出站温度策略。"""
    from domains.gateway.domain.upstream_profile_registry import get_upstream_profile

    profile = get_upstream_profile(credential_profile_id, provider=provider)
    fixed = profile.fixed_outbound_temperature
    if fixed is None:
        return None
    if fixed == 1.0:
        return TEMPERATURE_POLICY_FIXED_1
    if fixed == 0.0:
        return TEMPERATURE_POLICY_PROBE_0
    return None


def _effective_upstream_profile_id(
    tags: dict[str, Any],
    *,
    credential_profile_id: str | None,
) -> str | None:
    if credential_profile_id and credential_profile_id.strip():
        return credential_profile_id.strip()
    raw = tags.get(UPSTREAM_PROFILE_ID_TAG)
    return raw.strip() if isinstance(raw, str) and raw.strip() else None


def infer_temperature_policy(
    *,
    thinking_param: str,
    supports_reasoning: bool = False,
    explicit: str | None = None,
    real_model: str = "",
    credential_profile_id: str | None = None,
    provider: str = "",
) -> str:
    """推断温度策略；Profile 硬约束优先于 tags 显式 ``client``。"""
    _ = real_model  # 保留入参供调用方扩展；当前以 profile 为 SSOT
    profile_policy = temperature_policy_from_upstream_profile(
        credential_profile_id=credential_profile_id,
        provider=provider,
    )
    if profile_policy is not None:
        return profile_policy

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
    credential_profile_id: str | None = None,
    provider: str = "",
) -> str:
    """从 tags 解析 ``temperature_policy``。"""
    explicit = tags.get("temperature_policy")
    explicit_str = explicit if isinstance(explicit, str) else None
    supports_reasoning = bool(tags.get("supports_reasoning", False))
    if bool(tags.get("supports_reasoning_content", False)):
        supports_reasoning = True
    prov = str(tags.get("provider") or provider or "")
    profile_id = _effective_upstream_profile_id(
        tags, credential_profile_id=credential_profile_id
    )
    return infer_temperature_policy(
        thinking_param=thinking_param,
        supports_reasoning=supports_reasoning,
        explicit=explicit_str,
        real_model=real_model,
        credential_profile_id=profile_id,
        provider=prov,
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
        provider=str(merged.get("provider") or ""),
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
    "UPSTREAM_PROFILE_ID_TAG",
    "enrich_temperature_tags",
    "infer_temperature_policy",
    "resolve_temperature_default_from_tags",
    "resolve_temperature_policy_from_tags",
    "temperature_policy_from_upstream_profile",
]
