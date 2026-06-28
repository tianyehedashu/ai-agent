"""集成测试共享 fixture。

HTTP ``client`` / ``dev_client`` 将单条 ``db_session`` 注入 ``get_db``；Gateway 代理在
preflight 后 ``release_request_db_connection()`` 会 ``close()`` 该 session，导致后续
HTTP 请求或 ``reload_router(db_session)`` 出现 DetachedInstanceError / MissingGreenlet。
集成测场景由 mock 承接上游，无需释放连接池槽位，故统一 noop。

同一 ``db_session`` 串多个 HTTP 请求时，生产 ``_finalize_dependency_session`` 的
commit/rollback 会使后续 JWT ``read_token`` 查不到用户（401 TOKEN_ERROR）；集成测改为
仅 flush 待写入行，回滚由 ``db_session`` fixture 收尾统一处理。
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture(autouse=True)
def _integration_test_finalize_db_session(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _flush_writes_only(session: AsyncSession) -> None:
        from libs.db.database import clear_session_write_marker, session_has_pending_writes

        if session_has_pending_writes(session):
            await session.flush()
            clear_session_write_marker(session)

    monkeypatch.setattr(
        "libs.db.database._finalize_dependency_session",
        _flush_writes_only,
    )


@pytest.fixture(autouse=True)
def _keep_gateway_test_db_session_open(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _noop_release(_session: AsyncSession) -> None:
        return None

    targets = (
        "domains.gateway.application.proxy.proxy_chat_entries.release_request_db_connection",
        "domains.gateway.application.proxy.proxy_litellm_client.release_request_db_connection",
        "domains.gateway.presentation.streaming_session.release_request_db_connection",
    )
    for target in targets:
        monkeypatch.setattr(target, _noop_release)


@pytest.fixture(autouse=True)
def _keep_probe_test_db_session_open(monkeypatch: pytest.MonkeyPatch) -> None:
    """probe/批导入路径在长耗时上游 I/O 前 ``release_session_before_blocking_io``：
    有写入则 commit、只读则 rollback。集成测 ``db_session`` 跨请求共享 SAVEPOINT，
    commit/rollback 均会破坏后续请求 JWT ``read_token`` 可见性（401 TOKEN_ERROR）。
    改为 flush-only，保持行可见性同时不清掉 SAVEPOINT。
    """

    async def _flush_only_release(session: AsyncSession) -> bool:
        from libs.db.database import clear_session_write_marker, session_has_pending_writes

        if session_has_pending_writes(session):
            await session.flush()
            clear_session_write_marker(session)
        return False

    monkeypatch.setattr(
        "libs.db.session_lifecycle.release_session_before_blocking_io",
        _flush_only_release,
    )


@pytest.fixture(autouse=True)
def _skip_chat_router_request_session_rollback(monkeypatch: pytest.MonkeyPatch) -> None:
    """chat_router 在流式前 ``rollback_open_transaction(db)`` 释放请求级事务；
    集成测 ``db_session`` 跨 HTTP 请求共享同一 SAVEPOINT，rollback 会清掉前序请求
    flush 的行（如 REST 创建的 session），导致 stream_db 找不到。此处 noop，
    与 ``_integration_test_finalize_db_session`` 的 flush-only 策略一致。
    """

    async def _noop_rollback(_session: AsyncSession) -> None:
        return None

    monkeypatch.setattr(
        "domains.agent.presentation.chat_router.rollback_open_transaction",
        _noop_rollback,
    )
