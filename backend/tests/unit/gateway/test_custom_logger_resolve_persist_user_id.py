"""``_resolve_persist_user_id`` 从 vkey / 平台 Key / personal team owner 回填。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from domains.gateway.infrastructure.callbacks.custom_logger import _resolve_persist_user_id


@pytest.mark.asyncio
async def test_resolve_persist_user_id_prefers_metadata_user() -> None:
    uid = uuid.uuid4()
    resolved = await _resolve_persist_user_id(
        AsyncMock(),
        user_id=uid,
        vkey_id=None,
    )
    assert resolved == uid


@pytest.mark.asyncio
async def test_resolve_persist_user_id_from_personal_team_owner(monkeypatch) -> None:
    owner_id = uuid.uuid4()
    team_id = uuid.uuid4()
    team = MagicMock()
    team.kind = "personal"
    team.owner_user_id = owner_id
    team_service = MagicMock()
    team_service.get_team = AsyncMock(return_value=team)
    monkeypatch.setattr(
        "domains.tenancy.application.team_service.TeamService",
        lambda _session: team_service,
    )
    resolved = await _resolve_persist_user_id(
        AsyncMock(),
        user_id=None,
        vkey_id=None,
        team_id=team_id,
    )
    assert resolved == owner_id
