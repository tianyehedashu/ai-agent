"""Small AsyncSession lifecycle helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from libs.db.database import (
    _commit_or_raise,
    clear_session_write_marker,
    commit_pending_writes,
    session_has_pending_writes,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def rollback_open_transaction(session: AsyncSession) -> None:
    """Rollback an open transaction when no later work depends on it."""
    if session.in_transaction():
        await session.rollback()


async def release_session_before_blocking_io(session: AsyncSession) -> bool:
    """在长耗时外部 I/O（上游探测、LLM/厂商 API）前结束当前 DB 事务。

    - 有待提交写入：``flush`` + ``commit``，释放行锁。
    - 只读未提交事务：``rollback``，避免 ``idle in transaction`` 占连接。

    Router 热重载等 **仅读库** 的场景请用 ``commit_pending_writes``，不必 rollback 只读段。
    """
    if not session.in_transaction():
        return False
    if session_has_pending_writes(session):
        await session.flush()
        await _commit_or_raise(session)
        clear_session_write_marker(session)
        return True
    await session.rollback()
    return False


async def release_request_db_connection(session: AsyncSession) -> None:
    """结束请求级 DB 占用：回滚未提交事务并将连接归还连接池。

    Gateway 代理在 preflight 完成后进入长耗时上游调用；若仅 rollback 而不 close，
    FastAPI ``get_db`` 仍占住 pool 槽位直至整包响应结束，高并发下会排队并触发 504。
    """
    await rollback_open_transaction(session)
    await session.close()


__all__ = [
    "commit_pending_writes",
    "release_request_db_connection",
    "release_session_before_blocking_io",
    "rollback_open_transaction",
]
