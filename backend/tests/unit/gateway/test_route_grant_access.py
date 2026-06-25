"""route_grant_access 纯规则（RBAC + 暴露别名）单测。"""

from __future__ import annotations

import uuid

import pytest

from domains.gateway.domain.errors import ManagementEntityNotFoundError
from domains.gateway.domain.policies.route_grant_access import (
    actor_owns_route,
    assert_actor_owns_route,
    assert_alias_free_in_team,
    assert_can_revoke_route_grant,
    assert_local_name_free_of_grant_alias,
    normalize_exposed_alias,
)
from libs.exceptions import TeamPermissionDeniedError, ValidationError


def test_actor_owns_route_only_creator() -> None:
    owner = uuid.uuid4()
    other = uuid.uuid4()
    assert actor_owns_route(route_created_by_user_id=owner, actor_user_id=owner) is True
    assert actor_owns_route(route_created_by_user_id=owner, actor_user_id=other) is False
    assert actor_owns_route(route_created_by_user_id=None, actor_user_id=owner) is False
    assert actor_owns_route(route_created_by_user_id=owner, actor_user_id=None) is False


def test_assert_actor_owns_route_hides_others_as_not_found() -> None:
    rid = str(uuid.uuid4())
    with pytest.raises(ManagementEntityNotFoundError):
        assert_actor_owns_route(
            route_id=rid,
            route_created_by_user_id=uuid.uuid4(),
            actor_user_id=uuid.uuid4(),
        )


def test_revoke_allowed_for_owner_or_team_admin() -> None:
    owner = uuid.uuid4()
    # 创建者本人
    assert_can_revoke_route_grant(
        route_created_by_user_id=owner, actor_user_id=owner, actor_team_role=None
    )
    # 目标团队管理员（非创建者）
    assert_can_revoke_route_grant(
        route_created_by_user_id=owner, actor_user_id=uuid.uuid4(), actor_team_role="admin"
    )
    # 既非创建者亦非管理员 → 拒绝
    with pytest.raises(TeamPermissionDeniedError):
        assert_can_revoke_route_grant(
            route_created_by_user_id=owner,
            actor_user_id=uuid.uuid4(),
            actor_team_role="member",
        )


def test_normalize_exposed_alias_fallback_and_validation() -> None:
    assert normalize_exposed_alias(None, default="vm") == "vm"
    assert normalize_exposed_alias("  custom ", default="vm") == "custom"
    with pytest.raises(ValidationError):
        normalize_exposed_alias("   ", default="  ")
    with pytest.raises(ValidationError):
        normalize_exposed_alias("x" * 201, default="vm")


def test_alias_collision_rules() -> None:
    # 与本地模型同名
    with pytest.raises(ValidationError):
        assert_alias_free_in_team(
            "a",
            local_model_names={"a"},
            local_route_virtual_models=set(),
            other_grant_alias_in_use=False,
        )
    # 与本地路由同名
    with pytest.raises(ValidationError):
        assert_alias_free_in_team(
            "r",
            local_model_names=set(),
            local_route_virtual_models={"r"},
            other_grant_alias_in_use=False,
        )
    # 被其它 grant 占用
    with pytest.raises(ValidationError):
        assert_alias_free_in_team(
            "g",
            local_model_names=set(),
            local_route_virtual_models=set(),
            other_grant_alias_in_use=True,
        )
    # 无冲突放行
    assert_alias_free_in_team(
        "ok",
        local_model_names={"x"},
        local_route_virtual_models={"y"},
        other_grant_alias_in_use=False,
    )


def test_local_name_free_of_grant_alias() -> None:
    assert_local_name_free_of_grant_alias("m", grant_alias_in_use=False, kind="model")
    with pytest.raises(ValidationError):
        assert_local_name_free_of_grant_alias("m", grant_alias_in_use=True, kind="model")
    with pytest.raises(ValidationError):
        assert_local_name_free_of_grant_alias("r", grant_alias_in_use=True, kind="route")
