"""网关代理鉴权：Bearer 与 x-api-key 解析。"""

from __future__ import annotations

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
import pytest

from domains.gateway.presentation.deps import pick_gateway_proxy_plain_token


def test_pick_token_prefers_bearer_over_x_api_key() -> None:
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="sk-gw-from-bearer")
    assert pick_gateway_proxy_plain_token(creds, "sk-gw-from-header") == "sk-gw-from-bearer"


def test_pick_token_falls_back_to_x_api_key() -> None:
    assert pick_gateway_proxy_plain_token(None, "  sk-gw-only  ") == "sk-gw-only"


def test_pick_token_bearer_only() -> None:
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="token")
    assert pick_gateway_proxy_plain_token(creds, None) == "token"


def test_pick_token_missing_raises() -> None:
    with pytest.raises(HTTPException) as ei:
        pick_gateway_proxy_plain_token(None, None)
    assert ei.value.status_code == 401
