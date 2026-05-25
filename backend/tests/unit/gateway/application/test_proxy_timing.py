"""Unit tests for gateway proxy timing headers."""

from domains.gateway.application.proxy_timing import (
    HEADER_GATEWAY_PREFLIGHT_MS,
    HEADER_GATEWAY_UPSTREAM_MS,
    GatewayProxyTiming,
    timing_response_headers,
)


def test_timing_response_headers_non_stream() -> None:
    headers = timing_response_headers(
        GatewayProxyTiming(preflight_ms=120, upstream_ms=7100)
    )
    assert headers == {
        HEADER_GATEWAY_PREFLIGHT_MS: "120",
        HEADER_GATEWAY_UPSTREAM_MS: "7100",
    }


def test_timing_response_headers_stream_preflight_only() -> None:
    headers = timing_response_headers(GatewayProxyTiming(preflight_ms=95))
    assert headers == {HEADER_GATEWAY_PREFLIGHT_MS: "95"}
    assert HEADER_GATEWAY_UPSTREAM_MS not in headers


def test_timing_response_headers_none() -> None:
    assert timing_response_headers(None) == {}
