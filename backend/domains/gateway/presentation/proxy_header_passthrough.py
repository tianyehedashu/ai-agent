"""入站 HTTP 头 → LiteLLM ``extra_headers`` 白名单透传。"""

from __future__ import annotations

from collections.abc import Mapping

from domains.gateway.domain.proxy.http_header_merge import merge_comma_separated_header_values

# 不透传到上游（鉴权 / 网关控制面）
_BLOCKED_HEADER_NAMES: frozenset[str] = frozenset(
    {
        "authorization",
        "x-api-key",
        "x-team-id",
        "host",
        "content-length",
        "content-type",
        "connection",
        "accept-encoding",
        "user-agent",
    }
)

# 允许透传（小写 HTTP 头名）
_PASSTHROUGH_EXACT: frozenset[str] = frozenset(
    {
        "anthropic-version",
        "anthropic-beta",
        "openai-beta",
    }
)


def _normalize_header_name(name: str) -> str:
    return name.strip().lower()


def is_passthrough_request_header(name: str) -> bool:
    """是否应将入站头写入 ``extra_headers``。"""
    key = _normalize_header_name(name)
    if key in _BLOCKED_HEADER_NAMES:
        return False
    if key in _PASSTHROUGH_EXACT:
        return True
    if key.startswith("x-stainless-"):
        return False
    if key.startswith("x-gateway-"):
        return False
    return False


def merge_extra_headers_from_request(
    body: dict[str, object],
    request_headers: Mapping[str, str],
) -> None:
    """把白名单请求头合并进 ``body['extra_headers']``（就地修改）。"""
    extra: dict[str, str] = {}
    existing = body.get("extra_headers")
    if isinstance(existing, dict):
        for k, v in existing.items():
            if isinstance(k, str) and v is not None:
                extra[k] = str(v)

    for name, value in request_headers.items():
        if not is_passthrough_request_header(name):
            continue
        if value is None or str(value).strip() == "":
            continue
        key = _normalize_header_name(name)
        if key == "anthropic-beta" and key in extra:
            extra[key] = merge_comma_separated_header_values(extra[key], str(value))
        else:
            extra[key] = str(value)

    if extra:
        body["extra_headers"] = extra


__all__ = [
    "is_passthrough_request_header",
    "merge_extra_headers_from_request",
]
