"""OpenAI 兼容代理试调/诊断用耗时拆分（响应头，非 OpenAI 标准字段）。"""

from __future__ import annotations

from dataclasses import dataclass

HEADER_GATEWAY_PREFLIGHT_MS = "X-Gateway-Preflight-Ms"
HEADER_GATEWAY_UPSTREAM_MS = "X-Gateway-Upstream-Ms"


@dataclass(frozen=True)
class GatewayProxyTiming:
    """单次 chat 代理的网关内耗时（不含浏览器↔网关网络）。"""

    preflight_ms: int
    upstream_ms: int | None = None


def timing_response_headers(timing: GatewayProxyTiming | None) -> dict[str, str]:
    """将 ``GatewayProxyTiming`` 转为 HTTP 响应头。"""
    if timing is None:
        return {}
    headers: dict[str, str] = {
        HEADER_GATEWAY_PREFLIGHT_MS: str(max(0, timing.preflight_ms)),
    }
    if timing.upstream_ms is not None:
        headers[HEADER_GATEWAY_UPSTREAM_MS] = str(max(0, timing.upstream_ms))
    return headers


__all__ = [
    "HEADER_GATEWAY_PREFLIGHT_MS",
    "HEADER_GATEWAY_UPSTREAM_MS",
    "GatewayProxyTiming",
    "timing_response_headers",
]
