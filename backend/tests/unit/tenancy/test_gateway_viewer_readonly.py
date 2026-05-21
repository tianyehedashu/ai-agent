"""Gateway 管理面：平台 viewer 仅允许读方法。"""

from __future__ import annotations

import pytest
from starlette.requests import Request

from domains.tenancy.presentation.team_dependencies import _assert_gateway_not_viewer_write
from libs.exceptions import PermissionDeniedError


def _request(method: str) -> Request:
    scope = {
        "type": "http",
        "method": method,
        "path": "/api/v1/gateway/keys",
        "headers": [],
    }
    return Request(scope)


@pytest.mark.unit
def test_viewer_allows_get() -> None:
    _assert_gateway_not_viewer_write(_request("GET"), "viewer")


@pytest.mark.unit
def test_viewer_blocks_post() -> None:
    with pytest.raises(PermissionDeniedError):
        _assert_gateway_not_viewer_write(_request("POST"), "viewer")


@pytest.mark.unit
def test_user_allows_post() -> None:
    _assert_gateway_not_viewer_write(_request("POST"), "user")
