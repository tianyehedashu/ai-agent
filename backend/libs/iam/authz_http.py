"""授权相关领域异常 → HTTP（横切映射）。"""

from __future__ import annotations

from fastapi import HTTPException

from libs.exceptions import PermissionDeniedError
from libs.iam.team_http import map_team_access_exception_to_http


def map_authz_error_to_http(exc: Exception) -> HTTPException | None:
    """团队访问、平台权限等 → HTTPException。"""
    mapped = map_team_access_exception_to_http(exc)
    if mapped is not None:
        return mapped
    if isinstance(exc, PermissionDeniedError):
        return HTTPException(status_code=403, detail=exc.message)
    return None


__all__ = ["map_authz_error_to_http"]
