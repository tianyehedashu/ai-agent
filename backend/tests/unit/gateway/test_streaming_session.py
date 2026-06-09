"""Gateway streaming session helper tests."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest

from domains.gateway.presentation.streaming_session import release_request_db_before_stream

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class _FakeSession:
    def __init__(self, *, active: bool) -> None:
        self._active = active
        self.rollback_calls = 0

    def in_transaction(self) -> bool:
        return self._active

    async def rollback(self) -> None:
        self.rollback_calls += 1
        self._active = False


@pytest.mark.asyncio
async def test_release_request_db_before_stream_rolls_back_active_transaction() -> None:
    session = _FakeSession(active=True)

    await release_request_db_before_stream(cast("AsyncSession", session))

    assert session.rollback_calls == 1
    assert session.in_transaction() is False


@pytest.mark.asyncio
async def test_release_request_db_before_stream_skips_inactive_transaction() -> None:
    session = _FakeSession(active=False)

    await release_request_db_before_stream(cast("AsyncSession", session))

    assert session.rollback_calls == 0
