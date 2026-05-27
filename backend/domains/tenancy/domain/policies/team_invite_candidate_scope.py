"""团队邀请候选人可见范围（存于 gateway_teams.settings）。"""

from __future__ import annotations

from typing import Literal

InviteCandidateScope = Literal["all_users", "shared_teams"]

INVITE_CANDIDATE_SCOPE_ALL_USERS: InviteCandidateScope = "all_users"
INVITE_CANDIDATE_SCOPE_SHARED_TEAMS: InviteCandidateScope = "shared_teams"
SETTINGS_KEY = "invite_candidate_scope"


def parse_invite_candidate_scope(settings: dict[str, object] | None) -> InviteCandidateScope:
    """从团队 settings 解析邀请候选人可见范围，缺省为全站活跃用户。"""
    if not settings:
        return INVITE_CANDIDATE_SCOPE_ALL_USERS
    raw = settings.get(SETTINGS_KEY)
    if raw == INVITE_CANDIDATE_SCOPE_SHARED_TEAMS:
        return INVITE_CANDIDATE_SCOPE_SHARED_TEAMS
    return INVITE_CANDIDATE_SCOPE_ALL_USERS


def normalize_invite_candidate_scope_for_settings(
    settings: dict[str, object] | None,
    *,
    invite_candidate_scope: InviteCandidateScope | None,
) -> dict[str, object] | None:
    """合并 invite_candidate_scope 到 settings；None 表示不修改该键。"""
    if invite_candidate_scope is None:
        return settings
    merged: dict[str, object] = dict(settings) if settings else {}
    merged[SETTINGS_KEY] = invite_candidate_scope
    return merged


def validate_invite_candidate_scope_value(value: object) -> InviteCandidateScope:
    """校验 settings 中的 invite_candidate_scope 枚举。"""
    if value == INVITE_CANDIDATE_SCOPE_SHARED_TEAMS:
        return INVITE_CANDIDATE_SCOPE_SHARED_TEAMS
    if value == INVITE_CANDIDATE_SCOPE_ALL_USERS:
        return INVITE_CANDIDATE_SCOPE_ALL_USERS
    raise ValueError(
        f"Invalid {SETTINGS_KEY}; expected 'all_users' or 'shared_teams'"
    )


__all__ = [
    "INVITE_CANDIDATE_SCOPE_ALL_USERS",
    "INVITE_CANDIDATE_SCOPE_SHARED_TEAMS",
    "SETTINGS_KEY",
    "InviteCandidateScope",
    "normalize_invite_candidate_scope_for_settings",
    "parse_invite_candidate_scope",
    "validate_invite_candidate_scope_value",
]
