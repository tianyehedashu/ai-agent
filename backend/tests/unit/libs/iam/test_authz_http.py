"""libs.iam.authz_http 映射测试。"""

from __future__ import annotations

from fastapi import status
import pytest

from libs.exceptions import PermissionDeniedError, TeamPermissionDeniedError
from libs.iam.authz_http import map_authz_error_to_problem


@pytest.mark.unit
def test_map_team_permission_denied() -> None:
    exc = TeamPermissionDeniedError("team-1")
    ctx = map_authz_error_to_problem(exc)
    assert ctx is not None
    assert ctx.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.unit
def test_map_permission_denied() -> None:
    exc = PermissionDeniedError(message="denied", resource="Session")
    ctx = map_authz_error_to_problem(exc)
    assert ctx is not None
    assert ctx.status_code == status.HTTP_403_FORBIDDEN
    assert ctx.detail == "denied"


@pytest.mark.unit
def test_map_unknown_returns_none() -> None:
    assert map_authz_error_to_problem(ValueError("x")) is None
