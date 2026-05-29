"""Tests for the Docker CLI availability probe."""

from __future__ import annotations

from unittest.mock import patch

from domains.agent.infrastructure.sandbox.docker_availability import docker_cli_available


def test_docker_cli_available_true() -> None:
    with patch(
        "domains.agent.infrastructure.sandbox.docker_availability.shutil.which",
        return_value="/usr/bin/docker",
    ):
        assert docker_cli_available() is True


def test_docker_cli_available_false() -> None:
    with patch(
        "domains.agent.infrastructure.sandbox.docker_availability.shutil.which",
        return_value=None,
    ):
        assert docker_cli_available() is False
