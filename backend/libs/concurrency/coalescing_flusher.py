"""通用「窗口合并刷写」器：进程内按键累加增量，由单个 flusher 周期性批量落库。

适用于「同一行被高频 ``UPDATE ... col = col + Δ``」的写热点：PostgreSQL 行级排他锁会把
并发更新串行化，高 QPS 下产生大量「等锁」慢查询。改为进程内按键合并增量、按窗口批量落库后，
同一键在一个刷写窗口内最多 1 条 UPDATE，消除行锁串行化，并把无上限的 fire-and-forget
``create_task`` 收敛为单个 flusher，避免占满后台连接池。

与具体业务解耦：调用方提供
- ``merge``：把新增量并入已累计值（须可结合/可交换，如「相加」「取较大时间戳」），失败并回时复用；
- ``flush``：把一批 ``(key, value)`` 原子落库；
- ``interval`` / ``max_pending``：实时读配置（0 间隔由调用方负责降级，不在此处理）；
- ``register_task``（可选）：登记内部 flusher / 一次性刷写任务，便于进程/测试 teardown 收口。

单线程事件循环下，``add`` 与 ``_flush`` 的字典换出均不跨 ``await``，无需额外加锁。
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Hashable
from typing import Generic, TypeVar

from utils.logging import get_logger

logger = get_logger(__name__)

K = TypeVar("K", bound=Hashable)
V = TypeVar("V")

TaskRegister = Callable[[asyncio.Task[None]], None]


class CoalescingFlusher(Generic[K, V]):
    """按键合并增量、单 flusher 周期批量刷写。"""

    def __init__(
        self,
        *,
        name: str,
        merge: Callable[[V, V], V],
        flush: Callable[[list[tuple[K, V]]], Awaitable[None]],
        interval_seconds: Callable[[], float],
        max_pending: Callable[[], int],
        register_task: TaskRegister | None = None,
    ) -> None:
        self._name = name
        self._merge = merge
        self._flush_batch = flush
        self._interval_seconds = interval_seconds
        self._max_pending = max_pending
        self._register_task = register_task
        self._pending: dict[K, V] = {}
        self._flusher: asyncio.Task[None] | None = None

    def add(self, key: K, value: V) -> None:
        """累加一个增量；惰性启动 flusher，超阈值时立即补刷。"""
        existing = self._pending.get(key)
        self._pending[key] = value if existing is None else self._merge(existing, value)
        self._ensure_flusher()
        if len(self._pending) >= max(1, self._max_pending()):
            self._schedule_oneoff_flush()

    def _register(self, task: asyncio.Task[None]) -> None:
        if self._register_task is not None:
            self._register_task(task)

    def _ensure_flusher(self) -> None:
        """惰性启动 flusher，绑定到当前事件循环（兼容多 worker / 测试逐用例换循环）。"""
        if self._flusher is not None and not self._flusher.done():
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        self._flusher = loop.create_task(self._run())
        self._register(self._flusher)

    def flush_soon(self) -> None:
        """请求立即补刷一次（关闭合并时由调用方触发，等价即时落库）。"""
        self._schedule_oneoff_flush()

    def _schedule_oneoff_flush(self) -> None:
        """待刷规模超阈值时立即补一次刷写（并发 flush 因原子换出而安全）。"""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        task = loop.create_task(self._flush())
        self._register(task)

    async def _run(self) -> None:
        interval = max(0.1, float(self._interval_seconds()))
        try:
            while True:
                await asyncio.sleep(interval)
                await self._flush()
        finally:
            # 关停 / 取消时排空，避免丢失增量。
            await self._flush()

    async def _flush(self) -> None:
        if not self._pending:
            return
        # 原子换出：读取与置空之间无 await，单线程下并发 flush 仅一方拿到快照。
        snapshot = self._pending
        self._pending = {}
        entries = list(snapshot.items())
        try:
            await self._flush_batch(entries)
        except Exception:
            logger.exception("Coalescing flush failed name=%s keys=%d", self._name, len(entries))
            self._merge_back(snapshot)

    def _merge_back(self, snapshot: dict[K, V]) -> None:
        """落库失败时把增量并回 pending，下个窗口重试，保证最终一致。"""
        for key, value in snapshot.items():
            existing = self._pending.get(key)
            self._pending[key] = value if existing is None else self._merge(existing, value)


__all__ = ["CoalescingFlusher", "TaskRegister"]
