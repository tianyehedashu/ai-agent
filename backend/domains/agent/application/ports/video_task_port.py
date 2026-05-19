"""Video task application port."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import uuid


class VideoTaskApplicationPort(Protocol):
    """Video task application capabilities exposed cross-domain."""

    async def reassign_anonymous_to_user(
        self,
        *,
        user_id: uuid.UUID | str,
        anonymous_user_id: str,
    ) -> int:
        """Reassign anonymous video tasks to a registered user."""
        ...


__all__ = ["VideoTaskApplicationPort"]
