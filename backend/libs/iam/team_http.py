"""团队访问相关领域异常 → HTTP（无 gateway 依赖，供 tenancy presentation 等复用）。"""

from __future__ import annotations

from fastapi import HTTPException, status

from libs.exceptions import (
    PersonalTeamNotInitializedError,
    TeamNotFoundError,
    TeamPermissionDeniedError,
)


def map_team_access_exception_to_http(exc: Exception) -> HTTPException | None:
    """若为团队访问类错误则返回对应 HTTPException，否则返回 None。"""
    if isinstance(exc, TeamNotFoundError):
        return HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, TeamPermissionDeniedError):
        return HTTPException(status.HTTP_403_FORBIDDEN, detail=str(exc))
    if isinstance(exc, PersonalTeamNotInitializedError):
        return HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )
    return None


__all__ = ["map_team_access_exception_to_http"]
