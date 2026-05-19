"""Identity application ports.

Ports declared here are the public application-layer contracts offered by the
identity domain to other bounded contexts.
"""

from __future__ import annotations

from typing import Protocol


class IdentityApplicationPort(Protocol):
    """Identity application capabilities exposed cross-domain."""

    async def count_users(self) -> int:
        """Count registered users."""
        ...


__all__ = ["IdentityApplicationPort"]
