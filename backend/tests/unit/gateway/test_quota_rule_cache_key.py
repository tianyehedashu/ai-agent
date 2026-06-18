"""配额规则缓存键隔离单测。

回归防护：非管理员列表按 actor 过滤，缓存键必须含 actor_user_id，
否则同团队同角色成员串号（看到他人配额 / 看不到自己的）。
"""

from __future__ import annotations

import uuid

from domains.gateway.application.management.quota_rule_cache import build_actor_role_hash


class TestQuotaRuleCacheKey:
    def test_member_hash_isolated_per_actor(self) -> None:
        user_a = uuid.uuid4()
        user_b = uuid.uuid4()

        hash_a = build_actor_role_hash(
            is_team_admin=False,
            is_platform_admin=False,
            team_role="member",
            actor_user_id=user_a,
        )
        hash_b = build_actor_role_hash(
            is_team_admin=False,
            is_platform_admin=False,
            team_role="member",
            actor_user_id=user_b,
        )
        assert hash_a != hash_b

    def test_admin_hash_shared_across_actors(self) -> None:
        hash_a = build_actor_role_hash(
            is_team_admin=True,
            is_platform_admin=False,
            team_role="admin",
            actor_user_id=uuid.uuid4(),
        )
        hash_b = build_actor_role_hash(
            is_team_admin=True,
            is_platform_admin=False,
            team_role="admin",
            actor_user_id=uuid.uuid4(),
        )
        assert hash_a == hash_b

    def test_same_member_actor_hash_stable(self) -> None:
        user = uuid.uuid4()
        assert build_actor_role_hash(
            is_team_admin=False,
            is_platform_admin=False,
            team_role="member",
            actor_user_id=user,
        ) == build_actor_role_hash(
            is_team_admin=False,
            is_platform_admin=False,
            team_role="member",
            actor_user_id=user,
        )
