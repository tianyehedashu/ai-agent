"""非 Token 能力的上游成本解析纯规则。"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

from domains.gateway.domain.types import GatewayCapability

BillingMode = Literal["token", "per_request", "hybrid"]

# LiteLLM model_cost 扩展键（与 upstream_model_pricing.extra 对齐）
NON_TOKEN_LITELLM_EXTRA_KEYS: frozenset[str] = frozenset(
    {
        "input_cost_per_image",
        "output_cost_per_image",
        "input_cost_per_second",
        "output_cost_per_second",
        "input_cost_per_audio_token",
        "output_cost_per_audio_token",
    }
)

_PER_REQUEST_CAPABILITIES: frozenset[str] = frozenset(
    {
        GatewayCapability.AUDIO_SPEECH.value,
        GatewayCapability.RERANK.value,
        GatewayCapability.MODERATION.value,
    }
)

_HYBRID_CAPABILITIES: frozenset[str] = frozenset(
    {
        GatewayCapability.IMAGE.value,
        GatewayCapability.VIDEO_GENERATION.value,
        GatewayCapability.AUDIO_TRANSCRIPTION.value,
    }
)


def capability_default_billing_mode(capability: str) -> BillingMode:
    cap = capability.strip().lower()
    if cap in _PER_REQUEST_CAPABILITIES:
        return "per_request"
    if cap in _HYBRID_CAPABILITIES:
        return "hybrid"
    return "token"


def merge_non_token_extra_from_litellm(entry: dict[str, Any]) -> dict[str, float]:
    """从 LiteLLM ``model_cost`` 条目提取非 token 单价键。"""
    out: dict[str, float] = {}
    for key in NON_TOKEN_LITELLM_EXTRA_KEYS:
        raw = entry.get(key)
        if raw is not None:
            out[key] = float(raw)
    return out


def _response_image_count(response: Any) -> int:
    if response is None:
        return 0
    data = getattr(response, "data", None)
    if data is None and isinstance(response, dict):
        data = response.get("data")
    if isinstance(data, list):
        return len(data)
    return 1 if data is not None else 0


def _response_duration_seconds(response: Any) -> Decimal | None:
    if response is None:
        return None
    usage = getattr(response, "usage", None)
    if usage is None and isinstance(response, dict):
        usage = response.get("usage")
    if not isinstance(usage, dict):
        return None
    for key in ("seconds", "duration_seconds", "audio_duration"):
        raw = usage.get(key)
        if raw is not None:
            return Decimal(str(raw))
    return None


def estimate_non_token_cost_from_extra(
    extra: dict[str, Any],
    response: Any,
    *,
    requests: int = 1,
) -> Decimal | None:
    """按 extra 单价与响应结构估算上游成本（能算则算）。"""
    total = Decimal("0")
    counted = False

    per_image = extra.get("input_cost_per_image") or extra.get("output_cost_per_image")
    if per_image is not None:
        n = _response_image_count(response)
        if n > 0:
            total += Decimal(str(per_image)) * Decimal(n)
            counted = True

    per_second = extra.get("input_cost_per_second") or extra.get("output_cost_per_second")
    if per_second is not None:
        duration = _response_duration_seconds(response)
        if duration is not None and duration > 0:
            total += Decimal(str(per_second)) * duration
            counted = True

    if not counted and requests > 0:
        return None
    return total


__all__ = [
    "NON_TOKEN_LITELLM_EXTRA_KEYS",
    "BillingMode",
    "capability_default_billing_mode",
    "estimate_non_token_cost_from_extra",
    "merge_non_token_extra_from_litellm",
]
