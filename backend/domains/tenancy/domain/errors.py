"""Tenancy domain errors — team access and personal team lifecycle."""

from libs.exceptions.base import HttpMappableDomainError


class TeamNotFoundError(HttpMappableDomainError):
    """团队不存在"""

    def __init__(self, team_id: str) -> None:
        super().__init__(f"团队不存在: {team_id}")
        self.team_id = team_id


class TeamPermissionDeniedError(HttpMappableDomainError):
    """团队权限不足"""

    def __init__(self, team_id: str, required_role: str | None = None) -> None:
        msg = f"团队 {team_id} 权限不足"
        if required_role:
            msg += f"，需要角色: {required_role}"
        super().__init__(msg)
        self.team_id = team_id


class PersonalTeamNotInitializedError(HttpMappableDomainError):
    """用户 personal team 未初始化（管理面）"""

    def __init__(self) -> None:
        super().__init__("Personal team not initialized; please contact admin")


__all__ = [
    "PersonalTeamNotInitializedError",
    "TeamNotFoundError",
    "TeamPermissionDeniedError",
]
