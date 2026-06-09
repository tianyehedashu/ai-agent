"""Small AsyncSession lifecycle helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def rollback_open_transaction(session: AsyncSession) -> None:
    """Rollback an open transaction when no later work depends on it."""
    if session.in_transaction():
        await session.rollback()


__all__ = ["rollback_open_transaction"]
