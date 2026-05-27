"""OpenAI 兼容代理试调/诊断用耗时拆分（响应头，非 OpenAI 标准字段）。"""

from __future__ import annotations

from dataclasses import dataclass

HEADER_GATEWAY_PREFLIGHT_MS = "X-Gateway-Preflight-Ms"
HEADER_GATEWAY_UPSTREAM_MS = "X-Gateway-Upstream-Ms"
HEADER_GATEWAY_TIMING = "X-Gateway-Timing"


@dataclass
class ProxyPrepareTimings:
    """单次 chat 代理准备阶段的分段耗时（毫秒）。"""

    guard_ms: int = 0
    metadata_ms: int = 0
    pricing_ms: int = 0
    vision_ms: int = 0
    direct_decide_ms: int = 0

    @property
    def preflight_ms(self) -> int:
        return max(
            0,
            self.guard_ms
            + self.metadata_ms
            + self.pricing_ms
            + self.vision_ms
            + self.direct_decide_ms,
        )


@dataclass(frozen=True)
class GatewayProxyTiming:
    """单次 chat 代理的网关内耗时（不含浏览器↔网关网络）。"""

    preflight_ms: int
    upstream_ms: int | None = None
    guard_ms: int | None = None
    metadata_ms: int | None = None
    pricing_ms: int | None = None
    vision_ms: int | None = None
    direct_decide_ms: int | None = None

    @classmethod
    def from_prepare(
        cls,
        prepare: ProxyPrepareTimings,
        *,
        upstream_ms: int | None = None,
    ) -> GatewayProxyTiming:
        return cls(
            preflight_ms=prepare.preflight_ms,
            upstream_ms=upstream_ms,
            guard_ms=prepare.guard_ms,
            metadata_ms=prepare.metadata_ms,
            pricing_ms=prepare.pricing_ms,
            vision_ms=prepare.vision_ms,
            direct_decide_ms=prepare.direct_decide_ms,
        )


def format_timing_breakdown(timing: GatewayProxyTiming) -> str:
    """``guard=…;meta=…;pricing=…;vision=…;direct=…;upstream=…`` 格式。"""
    parts: list[str] = []
    if timing.guard_ms is not None:
        parts.append(f"guard={max(0, timing.guard_ms)}")
    if timing.metadata_ms is not None and timing.metadata_ms > 0:
        parts.append(f"meta={max(0, timing.metadata_ms)}")
    if timing.pricing_ms is not None and timing.pricing_ms > 0:
        parts.append(f"pricing={max(0, timing.pricing_ms)}")
    if timing.vision_ms is not None and timing.vision_ms > 0:
        parts.append(f"vision={max(0, timing.vision_ms)}")
    if timing.direct_decide_ms is not None and timing.direct_decide_ms > 0:
        parts.append(f"direct={max(0, timing.direct_decide_ms)}")
    if timing.upstream_ms is not None:
        parts.append(f"upstream={max(0, timing.upstream_ms)}")
    return ";".join(parts)


def timing_metadata_fields(timing: GatewayProxyTiming) -> dict[str, int | str]:
    """写入 ``gateway_request_logs.metadata`` 的分段耗时字段。"""
    fields: dict[str, int | str] = {
        "gateway_preflight_ms": max(0, timing.preflight_ms),
        "gateway_timing_breakdown": format_timing_breakdown(timing),
    }
    if timing.guard_ms is not None:
        fields["gateway_timing_guard_ms"] = max(0, timing.guard_ms)
    if timing.metadata_ms is not None:
        fields["gateway_timing_metadata_ms"] = max(0, timing.metadata_ms)
    if timing.pricing_ms is not None:
        fields["gateway_timing_pricing_ms"] = max(0, timing.pricing_ms)
    if timing.vision_ms is not None:
        fields["gateway_timing_vision_ms"] = max(0, timing.vision_ms)
    if timing.direct_decide_ms is not None:
        fields["gateway_timing_direct_ms"] = max(0, timing.direct_decide_ms)
    if timing.upstream_ms is not None:
        fields["gateway_timing_upstream_ms"] = max(0, timing.upstream_ms)
    return fields


def timing_response_headers(timing: GatewayProxyTiming | None) -> dict[str, str]:
    """将 ``GatewayProxyTiming`` 转为 HTTP 响应头。"""
    if timing is None:
        return {}
    headers: dict[str, str] = {
        HEADER_GATEWAY_PREFLIGHT_MS: str(max(0, timing.preflight_ms)),
    }
    breakdown = format_timing_breakdown(timing)
    if breakdown:
        headers[HEADER_GATEWAY_TIMING] = breakdown
    if timing.upstream_ms is not None:
        headers[HEADER_GATEWAY_UPSTREAM_MS] = str(max(0, timing.upstream_ms))
    return headers


__all__ = [
    "HEADER_GATEWAY_PREFLIGHT_MS",
    "HEADER_GATEWAY_TIMING",
    "HEADER_GATEWAY_UPSTREAM_MS",
    "GatewayProxyTiming",
    "ProxyPrepareTimings",
    "format_timing_breakdown",
    "timing_metadata_fields",
    "timing_response_headers",
]
