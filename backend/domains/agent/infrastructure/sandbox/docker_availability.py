"""Docker CLI availability probe (infrastructure IO)."""

from __future__ import annotations

import shutil


def docker_cli_available() -> bool:
    """Return True if ``docker`` is on PATH."""
    return shutil.which("docker") is not None
