"""Tests for sandbox runtime policy (pure functions)."""

from __future__ import annotations

from domains.agent.domain.sandbox_runtime_policy import (
    should_pre_create_persistent_sandbox,
    wants_persistent_docker_sandbox,
)
from libs.config.execution_config import (
    DockerConfig,
    ExecutionConfig,
    SandboxConfig,
    SandboxMode,
)


def _docker_config(*, sandbox_enabled: bool = True) -> ExecutionConfig:
    return ExecutionConfig(
        sandbox=SandboxConfig(
            mode=SandboxMode.DOCKER,
            docker=DockerConfig(sandbox_enabled=sandbox_enabled),
        ),
    )


class TestWantsPersistentDockerSandbox:
    def test_docker_mode_enabled(self) -> None:
        assert wants_persistent_docker_sandbox(_docker_config()) is True

    def test_docker_mode_disabled(self) -> None:
        assert wants_persistent_docker_sandbox(_docker_config(sandbox_enabled=False)) is False

    def test_local_mode(self) -> None:
        config = ExecutionConfig(
            sandbox=SandboxConfig(
                mode=SandboxMode.LOCAL,
                docker=DockerConfig(sandbox_enabled=True),
            ),
        )
        assert wants_persistent_docker_sandbox(config) is False


class TestShouldPreCreatePersistentSandbox:
    def test_wants_and_docker_present(self) -> None:
        assert (
            should_pre_create_persistent_sandbox(_docker_config(), docker_cli_present=True) is True
        )

    def test_wants_but_no_docker_cli(self) -> None:
        assert (
            should_pre_create_persistent_sandbox(_docker_config(), docker_cli_present=False)
            is False
        )

    def test_docker_present_but_local_mode(self) -> None:
        config = ExecutionConfig(
            sandbox=SandboxConfig(
                mode=SandboxMode.LOCAL,
                docker=DockerConfig(sandbox_enabled=True),
            ),
        )
        assert should_pre_create_persistent_sandbox(config, docker_cli_present=True) is False
