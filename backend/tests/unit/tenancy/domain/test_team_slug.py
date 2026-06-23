"""``domains.tenancy.domain.policies.team_slug`` 纯函数单测。"""

from __future__ import annotations

import uuid

from domains.tenancy.domain.policies.team_slug import PERSONAL_SLUG_PREFIX, personal_team_slug


def test_personal_team_slug_uses_first_8_hex() -> None:
    user_id = uuid.UUID("877ae63a-985c-4e4e-9425-986f79e944cc")
    assert personal_team_slug(user_id) == "personal-877ae63a"


def test_personal_team_slug_prefix_and_length() -> None:
    slug = personal_team_slug(uuid.uuid4())
    assert slug.startswith(PERSONAL_SLUG_PREFIX)
    # personal- + 8 位 hex
    assert len(slug) == len(PERSONAL_SLUG_PREFIX) + 8


def test_personal_team_slug_stable_for_same_user() -> None:
    user_id = uuid.uuid4()
    assert personal_team_slug(user_id) == personal_team_slug(user_id)
