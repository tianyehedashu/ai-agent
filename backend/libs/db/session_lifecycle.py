"""Small AsyncSession lifecycle helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def rollback_open_transaction(session: AsyncSession) -> None:
    """Rollback an open transaction when no later work depends on it."""
    if session.in_transaction():
        await session.rollback()


async def release_request_db_connection(session: AsyncSession) -> None:
    """结束请求级 DB 占用：回滚未提交事务并将连接归还连接池。

    Gateway 代理在 preflight 完成后进入长耗时上游调用；若仅 rollback 而不 close，
    FastAPI ``get_db`` 仍占住 pool 槽位直至整包响应结束，高并发下会排队并触发 504。
    """
    await rollback_open_transaction(session)
    await session.close()


__all__ = ["release_request_db_connection", "rollback_open_transaction"]
