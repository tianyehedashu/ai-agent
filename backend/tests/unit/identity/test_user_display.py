"""identity.application.user_display / ports 纯函数与解析单测。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from domains.identity.application.ports import UserSummaryView, user_display_label
from domains.identity.application.user_display import resolve_user_display_snapshot


def test_user_display_label_prefers_name() -> None:
    assert user_display_label(UserSummaryView(name="张三", email="a@b.com")) == "张三"


def test_user_display_label_falls_back_to_email() -> None:
    assert user_display_label(UserSummaryView(name=None, email="a@b.com")) == "a@b.com"


def test_user_display_label_none_for_missing() -> None:
    assert user_display_label(None) is None


@pytest.mark.asyncio
async def test_resolve_user_display_snapshot_delegates_to_port() -> None:
    uid = uuid.uuid4()
    port = MagicMock()
    port.list_summary_views_by_ids = AsyncMock(
        return_value={uid: UserSummaryView(name="Bob", email="bob@example.com")}
    )
    result = await resolve_user_display_snapshot(
        MagicMock(),
        uid,
        user_query=port,
    )
    assert result == "Bob"
    port.list_summary_views_by_ids.assert_awaited_once_with([uid])


@pytest.mark.asyncio
async def test_resolve_user_display_snapshot_none_without_user_id() -> None:
    assert await resolve_user_display_snapshot(MagicMock(), None) is None
