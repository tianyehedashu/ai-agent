"""DB session 生命周期回归测试。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from libs.db.database import (
    _finalize_dependency_session,
    _is_dirty_connection_error,
    _rollback_for_cleanup,
)


def _fake_session(*, has_writes: bool = False) -> SimpleNamespace:
    sync_session = SimpleNamespace(
        info={"_ai_agent_has_writes": True} if has_writes else {},
        new=[],
        dirty=[],
        deleted=[],
    )
    return SimpleNamespace(
        sync_session=sync_session,
        commit=AsyncMock(),
        rollback=AsyncMock(),
        invalidate=AsyncMock(),
    )


@pytest.mark.asyncio
async def test_dependency_session_rolls_back_read_only_request() -> None:
    session = _fake_session(has_writes=False)

    await _finalize_dependency_session(session)  # type: ignore[arg-type]

    session.rollback.assert_awaited_once()
    session.commit.assert_not_awaited()
    session.invalidate.assert_not_awaited()


@pytest.mark.asyncio
async def test_dependency_session_commits_when_request_has_writes() -> None:
    session = _fake_session(has_writes=True)

    await _finalize_dependency_session(session)  # type: ignore[arg-type]

    session.commit.assert_awaited_once()
    session.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_dirty_connection_is_invalidated_on_cleanup_rollback_failure() -> None:
    session = _fake_session()
    session.rollback.side_effect = RuntimeError(
        "cannot perform operation: another operation is in progress"
    )

    await _rollback_for_cleanup(session)  # type: ignore[arg-type]

    session.invalidate.assert_awaited_once()


def test_dirty_connection_detection_walks_exception_chain() -> None:
    root = RuntimeError("cannot use Connection.transaction() in a manually started transaction")
    wrapped = RuntimeError("outer")
    wrapped.__cause__ = root

    assert _is_dirty_connection_error(wrapped)
