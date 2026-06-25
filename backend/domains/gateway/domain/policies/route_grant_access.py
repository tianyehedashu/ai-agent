"""路由跨团队共享授权的纯规则（RBAC + 暴露别名）。

与 ``virtual_key_access`` / ``team_model_access`` 对齐：
- **创建 grant**：仅路由创建者本人（owner-only）。
- **移除 grant**：路由创建者本人 ∨ 目标团队 owner/admin（双向）。
- 平台 admin **无旁路**（对齐 vkey grant）。

别名冲突等需 DB 查询的部分由 application 层提供集合后调用纯判定函数。
"""

from __future__ import annotations

from uuid import UUID

from domains.gateway.domain.errors import ManagementEntityNotFoundError
from domains.tenancy.domain.policies.team_role import is_admin_or_owner_team_role
from libs.exceptions import TeamPermissionDeniedError, ValidationError

MAX_EXPOSED_ALIAS_LEN = 200


def actor_owns_route(*, route_created_by_user_id: UUID | None, actor_user_id: UUID | None) -> bool:
    """路由按创建者私有：仅 ``created_by_user_id == actor`` 可发布/改别名。"""
    if actor_user_id is None or route_created_by_user_id is None:
        return False
    return route_created_by_user_id == actor_user_id


def assert_actor_owns_route(
    *,
    route_id: str,
    route_created_by_user_id: UUID | None,
    actor_user_id: UUID | None,
) -> None:
    """非创建者一律按"不存在"处理（防枚举他人路由）。"""
    if not actor_owns_route(
        route_created_by_user_id=route_created_by_user_id,
        actor_user_id=actor_user_id,
    ):
        raise ManagementEntityNotFoundError("route", route_id)


def assert_can_revoke_route_grant(
    *,
    route_created_by_user_id: UUID | None,
    actor_user_id: UUID | None,
    actor_team_role: str | None,
) -> None:
    """移除 grant：创建者本人 ∨ 目标团队 owner/admin。"""
    if actor_owns_route(
        route_created_by_user_id=route_created_by_user_id,
        actor_user_id=actor_user_id,
    ):
        return
    if is_admin_or_owner_team_role(actor_team_role):
        return
    raise TeamPermissionDeniedError("仅路由创建者或团队管理员可移除该共享授权")


def normalize_exposed_alias(alias: str | None, *, default: str) -> str:
    """暴露别名规范化：空则回退 ``virtual_model``；校验非空与长度。"""
    cleaned = (alias or "").strip()
    if not cleaned:
        cleaned = (default or "").strip()
    if not cleaned:
        raise ValidationError("暴露别名不能为空")
    if len(cleaned) > MAX_EXPOSED_ALIAS_LEN:
        raise ValidationError(f"暴露别名过长（最大 {MAX_EXPOSED_ALIAS_LEN}）")
    return cleaned


def assert_alias_free_in_team(
    alias: str,
    *,
    local_model_names: set[str],
    local_route_virtual_models: set[str],
    other_grant_alias_in_use: bool,
) -> None:
    """暴露别名在团队 T 内须与本地 model / route / 其它 grant 别名互斥（双向唯一）。"""
    if alias in local_model_names:
        raise ValidationError(f"暴露别名 {alias!r} 与团队内已注册模型同名")
    if alias in local_route_virtual_models:
        raise ValidationError(f"暴露别名 {alias!r} 与团队内已有路由同名")
    if other_grant_alias_in_use:
        raise ValidationError(f"暴露别名 {alias!r} 已被该团队的其它共享路由占用")


def assert_local_name_free_of_grant_alias(
    name: str,
    *,
    grant_alias_in_use: bool,
    kind: str = "model",
) -> None:
    """本地创建 model/route 时反向校验：名字不得撞已存在的共享路由暴露别名。"""
    if grant_alias_in_use:
        label = "模型" if kind == "model" else "路由"
        raise ValidationError(f"{label}名 {name!r} 与团队内共享路由的暴露别名冲突")


__all__ = [
    "MAX_EXPOSED_ALIAS_LEN",
    "actor_owns_route",
    "assert_actor_owns_route",
    "assert_alias_free_in_team",
    "assert_can_revoke_route_grant",
    "assert_local_name_free_of_grant_alias",
    "normalize_exposed_alias",
]
