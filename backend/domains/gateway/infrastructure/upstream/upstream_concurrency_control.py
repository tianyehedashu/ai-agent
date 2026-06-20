"""上游并发控制：按 team+model 维度的 Semaphore + 简单断路器。

设计原则：
- 位于 infrastructure 层，不污染 application/presentation 接口。
- 按 (team_id, model) 维度维护 Semaphore，避免全局 semaphore 导致小团队被大团队阻塞。
- 简单断路器：连续失败达到阈值或时间窗口内失败率过高时打开，冷却后半开。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime

from bootstrap.config import settings
from domains.gateway.domain.errors import RateLimitExceededError
from utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class _CircuitState:
    """断路器状态（非线程安全，受外部 lock 保护）。"""

    failures: int = 0
    last_failure_time: float | None = None
    total_calls: int = 0
    total_failures: int = 0
    state: str = "closed"  # closed, open, half_open


class TeamModelConcurrencyController:
    """按 team+model 维度的并发控制器 + 断路器。"""

    def __init__(
        self,
        *,
        max_concurrent: int,
        circuit_failure_threshold: int,
        circuit_failure_rate: float,
        circuit_cooldown_seconds: float,
    ) -> None:
        self._max_concurrent = max_concurrent
        self._circuit_failure_threshold = circuit_failure_threshold
        self._circuit_failure_rate = circuit_failure_rate
        self._circuit_cooldown_seconds = circuit_cooldown_seconds
        self._semaphores: dict[tuple[str, str], asyncio.Semaphore] = {}
        self._circuit_states: dict[tuple[str, str], _CircuitState] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def _key(team_id: str, model: str) -> tuple[str, str]:
        return (team_id, model)

    async def _get_semaphore(self, team_id: str, model: str) -> asyncio.Semaphore:
        key = self._key(team_id, model)
        async with self._lock:
            sem = self._semaphores.get(key)
            if sem is None:
                sem = asyncio.Semaphore(self._max_concurrent)
                self._semaphores[key] = sem
            return sem

    def _check_circuit(self, state: _CircuitState) -> bool:
        """返回 True 表示允许通过（断路器关闭或半开）。"""
        if state.state == "closed":
            return True
        if state.state == "open":
            now = datetime.now(UTC).timestamp()
            if state.last_failure_time is not None and (
                now - state.last_failure_time
            ) > self._circuit_cooldown_seconds:
                state.state = "half_open"
                return True
            return False
        # half_open: 允许一个请求通过测试。
        return True

    async def acquire(self, team_id: str, model: str) -> None:
        """获取并发许可；断路器打开时直接抛出 RateLimitExceededError。"""
        key = self._key(team_id, model)

        async with self._lock:
            circuit = self._circuit_states.setdefault(key, _CircuitState())
            if not self._check_circuit(circuit):
                logger.warning(
                    "Circuit breaker OPEN for team=%s model=%s",
                    team_id,
                    model,
                )
                raise RateLimitExceededError(
                    scope=f"concurrency:{team_id}:{model}",
                    retry_after=int(self._circuit_cooldown_seconds),
                )

        sem = await self._get_semaphore(team_id, model)
        await sem.acquire()

    async def release(self, team_id: str, model: str) -> None:
        """释放并发许可。"""
        key = self._key(team_id, model)
        sem = self._semaphores.get(key)
        if sem is not None:
            sem.release()

    async def record_success(self, team_id: str, model: str) -> None:
        """记录成功，重置断路器失败计数。"""
        key = self._key(team_id, model)
        async with self._lock:
            circuit = self._circuit_states.get(key)
            if circuit is None:
                return
            circuit.failures = 0
            circuit.total_calls += 1
            if circuit.state == "half_open":
                circuit.state = "closed"
                logger.info(
                    "Circuit breaker CLOSED for team=%s model=%s",
                    team_id,
                    model,
                )

    async def record_failure(self, team_id: str, model: str) -> None:
        """记录失败，更新断路器状态。"""
        key = self._key(team_id, model)
        now = datetime.now(UTC).timestamp()

        async with self._lock:
            circuit = self._circuit_states.setdefault(key, _CircuitState())
            circuit.failures += 1
            circuit.total_failures += 1
            circuit.total_calls += 1
            circuit.last_failure_time = now

            failure_rate = circuit.total_failures / max(circuit.total_calls, 1)

            if (
                circuit.failures >= self._circuit_failure_threshold
                or failure_rate > self._circuit_failure_rate
            ) and circuit.state != "open":
                circuit.state = "open"
                logger.warning(
                    "Circuit breaker OPEN for team=%s model=%s "
                    "(failures=%d, rate=%.2f)",
                    team_id,
                    model,
                    circuit.failures,
                    failure_rate,
                )


_concurrency_controller: TeamModelConcurrencyController | None = None


def get_concurrency_controller() -> TeamModelConcurrencyController:
    """全局单例并发控制器。"""
    global _concurrency_controller  # pylint: disable=global-statement
    if _concurrency_controller is None:
        _concurrency_controller = TeamModelConcurrencyController(
            max_concurrent=max(1, getattr(settings, "gateway_max_concurrent_per_team_model", 10)),
            circuit_failure_threshold=max(
                1, getattr(settings, "gateway_circuit_failure_threshold", 5)
            ),
            circuit_failure_rate=min(
                1.0,
                max(0.0, getattr(settings, "gateway_circuit_failure_rate", 0.5)),
            ),
            circuit_cooldown_seconds=max(
                0.0, getattr(settings, "gateway_circuit_cooldown_seconds", 30.0)
            ),
        )
    return _concurrency_controller


def _reset_concurrency_controller_for_tests() -> None:  # type: ignore[reportUnusedFunction]
    """测试钩子：重置全局单例。"""
    global _concurrency_controller  # pylint: disable=global-statement
    _concurrency_controller = None


__all__ = [
    "TeamModelConcurrencyController",
    "get_concurrency_controller",
]
