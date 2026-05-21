"""libs.iam.authz_http 映射测试。"""

from __future__ import annotations

import pytest
from fastapi import HTTPException, status

from libs.exceptions import PermissionDeniedError, TeamPermissionDeniedError
from libs.iam.authz_http import map_authz_error_to_http


@pytest.mark.unit
def test_map_team_permission_denied() -> None:
    exc = TeamPermissionDeniedError("team-1")
    http_exc = map_authz_error_to_http(exc)
    assert http_exc is not None
    assert http_exc.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.unit
def test_map_permission_denied() -> None:
    exc = PermissionDeniedError(message="denied", resource="Session")
    http_exc = map_authz_error_to_http(exc)
    assert http_exc is not None
    assert http_exc.status_code == status.HTTP_403_FORBIDDEN
    assert http_exc.detail == "denied"


@pytest.mark.unit
def test_map_unknown_returns_none() -> None:
    assert map_authz_error_to_http(ValueError("x")) is None
