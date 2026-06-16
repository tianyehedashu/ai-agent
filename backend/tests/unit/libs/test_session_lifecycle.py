"""Session lifecycle helper tests."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest

from libs.db.session_lifecycle import release_request_db_connection

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class _FakeSession:
    def __init__(self, *, active: bool) -> None:
        self._active = active
        self.rollback_calls = 0
        self.close_calls = 0

    def in_transaction(self) -> bool:
        return self._active

    async def rollback(self) -> None:
        self.rollback_calls += 1
        self._active = False

    async def close(self) -> None:
        self.close_calls += 1


@pytest.mark.asyncio
async def test_release_request_db_connection_rolls_back_and_closes() -> None:
    session = _FakeSession(active=True)

    await release_request_db_connection(cast("AsyncSession", session))

    assert session.rollback_calls == 1
    assert session.close_calls == 1


@pytest.mark.asyncio
async def test_release_request_db_connection_closes_without_active_transaction() -> None:
    session = _FakeSession(active=False)

    await release_request_db_connection(cast("AsyncSession", session))

    assert session.rollback_calls == 0
    assert session.close_calls == 1
