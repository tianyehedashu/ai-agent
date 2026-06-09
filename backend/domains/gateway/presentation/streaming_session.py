"""Streaming response helpers for Gateway presentation endpoints."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from libs.db.session_lifecycle import rollback_open_transaction


async def release_request_db_before_stream(session: AsyncSession) -> None:
    """Release the request DB transaction before returning a long-lived stream.

    StreamingResponse keeps FastAPI yield dependencies alive until the client
    finishes reading the body. Gateway stream preparation has already copied the
    DB-backed state it needs into metadata, so keeping the SQL transaction open
    only leaves the connection idle in transaction while the upstream stream is
    running.
    """
    await rollback_open_transaction(session)


__all__ = ["release_request_db_before_stream"]
