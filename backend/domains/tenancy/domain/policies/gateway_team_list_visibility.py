"""Gateway 管理面平台 admin 团队列表可见性（纯函数）。"""

from __future__ import annotations

ANONYMOUS_USER_ROLE = "anonymous"


def is_visible_in_platform_admin_gateway_list(
    *,
    kind: str,
    owner_user_role: str,
) -> bool:
    """平台 admin 全站团队列表：shared 均可见；personal 排除匿名 shadow 用户。"""
    if kind != "personal":
        return True
    return owner_user_role != ANONYMOUS_USER_ROLE


__all__ = [
    "ANONYMOUS_USER_ROLE",
    "is_visible_in_platform_admin_gateway_list",
]
