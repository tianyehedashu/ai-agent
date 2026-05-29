"""Video task application port."""

from __future__ import annotations

from typing import Protocol


class VideoTaskApplicationPort(Protocol):
    """Video task application capabilities exposed cross-domain."""


__all__ = ["VideoTaskApplicationPort"]
