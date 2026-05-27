"""team_display_label.format_team_display_label"""

from __future__ import annotations

import uuid

from domains.tenancy.domain.team_display_label import format_team_display_label


def test_personal_workspace_for_owner() -> None:
    uid = uuid.uuid4()
    assert (
        format_team_display_label(
            kind="personal",
            name="Personal",
            owner_user_id=uid,
            viewer_user_id=uid,
        )
        == "个人工作区"
    )


def test_foreign_personal_team() -> None:
    owner = uuid.uuid4()
    viewer = uuid.uuid4()
    assert (
        format_team_display_label(
            kind="personal",
            name="Personal",
            owner_user_id=owner,
            viewer_user_id=viewer,
            owner_hint="alice@example.com",
        )
        == "个人 · alice@example.com"
    )


def test_shared_team_uses_name() -> None:
    assert (
        format_team_display_label(
            kind="shared",
            name="研发",
            owner_user_id=uuid.uuid4(),
            viewer_user_id=uuid.uuid4(),
        )
        == "研发"
    )
