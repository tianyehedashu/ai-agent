"""Streaming response helpers for Gateway presentation endpoints."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from libs.db.session_lifecycle import release_request_db_connection


async def release_request_db_before_stream(session: AsyncSession) -> None:
    """在上游长连接/流式响应前释放请求 DB 连接。

    StreamingResponse 会让 FastAPI 依赖存活到客户端读完 body，但 preflight 所需
    状态已写入 metadata；此处 close 将连接归还 pool，避免占槽排队。
    """
    await release_request_db_connection(session)


__all__ = ["release_request_db_before_stream"]
