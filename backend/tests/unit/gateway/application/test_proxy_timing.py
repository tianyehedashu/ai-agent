"""Unit tests for gateway proxy timing headers."""

from domains.gateway.application.proxy.proxy_timing import (
    HEADER_GATEWAY_PREFLIGHT_MS,
    HEADER_GATEWAY_TIMING,
    HEADER_GATEWAY_UPSTREAM_MS,
    GatewayProxyTiming,
    ProxyPrepareTimings,
    format_timing_breakdown,
    timing_response_headers,
)


def test_timing_response_headers_non_stream() -> None:
    prepare = ProxyPrepareTimings(
        guard_ms=40,
        metadata_ms=50,
        pricing_ms=20,
        direct_decide_ms=10,
    )
    headers = timing_response_headers(GatewayProxyTiming.from_prepare(prepare, upstream_ms=7100))
    assert headers[HEADER_GATEWAY_PREFLIGHT_MS] == "120"
    assert headers[HEADER_GATEWAY_UPSTREAM_MS] == "7100"
    assert headers[HEADER_GATEWAY_TIMING] == format_timing_breakdown(
        GatewayProxyTiming.from_prepare(prepare, upstream_ms=7100)
    )


def test_timing_response_headers_stream_preflight_only() -> None:
    prepare = ProxyPrepareTimings(guard_ms=95)
    headers = timing_response_headers(GatewayProxyTiming.from_prepare(prepare))
    assert headers == {
        HEADER_GATEWAY_PREFLIGHT_MS: "95",
        HEADER_GATEWAY_TIMING: "guard=95",
    }
    assert HEADER_GATEWAY_UPSTREAM_MS not in headers


def test_timing_response_headers_none() -> None:
    assert timing_response_headers(None) == {}
