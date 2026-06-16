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
        "domains.gateway.application.proxy_chat_entries.release_request_db_connection",
        "domains.gateway.application.proxy_litellm_client.release_request_db_connection",
        "domains.gateway.presentation.streaming_session.release_request_db_connection",
    )
    for target in targets:
        monkeypatch.setattr(target, _noop_release)
