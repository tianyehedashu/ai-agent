"""Tests for upstream_concurrency_control."""

from __future__ import annotations

import asyncio

import pytest

from domains.gateway.domain.errors import RateLimitExceededError
from domains.gateway.infrastructure.upstream.upstream_concurrency_control import (
    TeamModelConcurrencyController,
    _reset_concurrency_controller_for_tests,
    get_concurrency_controller,
)


@pytest.fixture
def controller() -> TeamModelConcurrencyController:
    _reset_concurrency_controller_for_tests()
    return TeamModelConcurrencyController(
        max_concurrent=2,
        circuit_failure_threshold=3,
        circuit_failure_rate=0.5,
        circuit_cooldown_seconds=0.1,
    )


@pytest.mark.asyncio
async def test_acquire_release_pair(controller: TeamModelConcurrencyController) -> None:
    await controller.acquire("team-1", "model-a")
    await controller.release("team-1", "model-a")


@pytest.mark.asyncio
async def test_concurrency_limit_blocks_same_team_model(
    controller: TeamModelConcurrencyController,
) -> None:
    await controller.acquire("team-1", "model-a")
    await controller.acquire("team-1", "model-a")

    # 第三个应阻塞；用 asyncio.wait_for 验证。
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(controller.acquire("team-1", "model-a"), timeout=0.05)

    await controller.release("team-1", "model-a")
    await controller.release("team-1", "model-a")


@pytest.mark.asyncio
async def test_different_team_model_not_blocked(
    controller: TeamModelConcurrencyController,
) -> None:
    await controller.acquire("team-1", "model-a")
    await controller.acquire("team-1", "model-a")
    # team-2 / model-a 不应被 team-1 阻塞。
    await controller.acquire("team-2", "model-a")
    await controller.release("team-2", "model-a")
    await controller.release("team-1", "model-a")
    await controller.release("team-1", "model-a")


@pytest.mark.asyncio
async def test_circuit_opens_after_consecutive_failures(
    controller: TeamModelConcurrencyController,
) -> None:
    for _ in range(3):
        await controller.record_failure("team-1", "model-a")

    with pytest.raises(RateLimitExceededError):
        await controller.acquire("team-1", "model-a")


@pytest.mark.asyncio
async def test_circuit_closes_after_success_in_half_open(
    controller: TeamModelConcurrencyController,
) -> None:
    for _ in range(3):
        await controller.record_failure("team-1", "model-a")

    with pytest.raises(RateLimitExceededError):
        await controller.acquire("team-1", "model-a")

    await asyncio.sleep(0.15)
    # 半开状态下允许一个请求通过；成功后关闭。
    await controller.acquire("team-1", "model-a")
    await controller.record_success("team-1", "model-a")
    await controller.acquire("team-1", "model-a")
    await controller.release("team-1", "model-a")
    await controller.release("team-1", "model-a")


@pytest.mark.asyncio
async def test_get_concurrency_controller_singleton() -> None:
    _reset_concurrency_controller_for_tests()
    first = get_concurrency_controller()
    second = get_concurrency_controller()
    assert first is second
