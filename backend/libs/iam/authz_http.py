"""授权相关领域异常 → ProblemContext（横切映射）。"""

from __future__ import annotations

from fastapi import status

from libs.api.problem_details import ProblemContext, default_title_for_status
from libs.exceptions import PermissionDeniedError
from libs.iam.team_http import map_team_access_exception_to_problem


def map_authz_error_to_problem(exc: Exception) -> ProblemContext | None:
    """团队访问、平台权限等 → ProblemContext。"""
    mapped = map_team_access_exception_to_problem(exc)
    if mapped is not None:
        return mapped
    if isinstance(exc, PermissionDeniedError):
        return ProblemContext(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=exc.message,
            title=default_title_for_status(status.HTTP_403_FORBIDDEN),
            code=exc.code,
            extra=exc.details or None,
        )
    return None


__all__ = ["map_authz_error_to_problem"]
