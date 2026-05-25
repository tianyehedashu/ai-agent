"""团队访问相关领域异常 → ProblemContext（无 gateway 依赖）。"""

from __future__ import annotations

from fastapi import status

from libs.api.problem_details import ProblemContext, default_title_for_status
from libs.exceptions import (
    PersonalTeamNotInitializedError,
    TeamNotFoundError,
    TeamPermissionDeniedError,
)
from libs.exceptions.codes import (
    PERSONAL_TEAM_NOT_INITIALIZED,
    TEAM_NOT_FOUND,
    TEAM_PERMISSION_DENIED,
)


def map_team_access_exception_to_problem(exc: Exception) -> ProblemContext | None:
    """若为团队访问类错误则返回 ProblemContext，否则 None。"""
    if isinstance(exc, TeamNotFoundError):
        return ProblemContext(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
            title=default_title_for_status(status.HTTP_404_NOT_FOUND),
            code=TEAM_NOT_FOUND,
        )
    if isinstance(exc, TeamPermissionDeniedError):
        return ProblemContext(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
            title=default_title_for_status(status.HTTP_403_FORBIDDEN),
            code=TEAM_PERMISSION_DENIED,
        )
    if isinstance(exc, PersonalTeamNotInitializedError):
        return ProblemContext(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
            title=default_title_for_status(status.HTTP_500_INTERNAL_SERVER_ERROR),
            code=PERSONAL_TEAM_NOT_INITIALIZED,
        )
    return None


__all__ = ["map_team_access_exception_to_problem"]
