"""有界延迟任务执行器：固定 worker 池 + 有界队列，治理 fire-and-forget 写入。

响应后的结算（按请求唯一、不可合并的任务）原先各自 ``asyncio.create_task``，
突发流量下无上限堆积：既抢占后台连接池、又让事件循环饥饿（拖垮 ``/health`` 探活），还可能 OOM。

本执行器从三个维度收口：
- **并发**：固定 ``max_workers`` 个常驻 worker，限制同时打 DB 的任务数；
- **驻留**：有界队列 ``max_queue``，限制内存中堆积的任务数；
- **背压**：队列满时 ``submit`` 先阻塞短超时等待空位，仍满则当场 inline 执行——
  把压力回传给调用方（极端过载时热路径轻微变慢），而非静默丢弃任务（不丢账）。

worker / 队列惰性绑定到当前事件循环，循环变更（多 worker 进程、测试逐用例换循环）时自动重建。
本类为纯技术原语：配置（worker 数 / 队列容量 / 阻塞超时）以可调用形式注入，实时读取。
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from contextlib import suppress

from utils.logging import get_logger

logger = get_logger(__name__)

JobFactory = Callable[[], Awaitable[None]]


class DeferredDbTaskRunner:
    """有界队列 + 固定 worker 池的延迟任务执行器。"""

    def __init__(
        self,
        *,
        name: str,
        max_workers: Callable[[], int],
        max_queue: Callable[[], int],
        submit_block_timeout_seconds: Callable[[], float],
        shutdown_drain_timeout_seconds: float = 10.0,
    ) -> None:
        self._name = name
        self._max_workers = max_workers
        self._max_queue = max_queue
        self._submit_block_timeout_seconds = submit_block_timeout_seconds
        self._shutdown_drain_timeout_seconds = shutdown_drain_timeout_seconds
        self._queue: asyncio.Queue[JobFactory] | None = None
        self._workers: list[asyncio.Task[None]] = []
        self._loop: asyncio.AbstractEventLoop | None = None

    def _ensure_started(self) -> asyncio.Queue[JobFactory]:
        """惰性在当前事件循环上建队列与 worker；循环变更或 worker 退出则重建。"""
        loop = asyncio.get_running_loop()
        alive = [w for w in self._workers if not w.done()]
        if self._loop is loop and self._queue is not None and alive:
            self._workers = alive
            return self._queue
        # 循环变更/首次/worker 全退出：在当前循环重建。
        self._loop = loop
        self._queue = asyncio.Queue(maxsize=max(1, self._max_queue()))
        self._workers = [
            loop.create_task(self._worker(self._queue)) for _ in range(max(1, self._max_workers()))
        ]
        return self._queue

    async def submit(self, job: JobFactory) -> None:
        """登记一个延迟任务：快路径入队；满载时阻塞短超时→仍满则 inline 执行。"""
        queue = self._ensure_started()
        try:
            queue.put_nowait(job)
            return
        except asyncio.QueueFull:
            pass
        timeout = self._submit_block_timeout_seconds()
        if timeout > 0:
            with suppress(asyncio.TimeoutError):
                await asyncio.wait_for(queue.put(job), timeout)
                return
        # 背压兜底：当场执行，宁可拖慢调用方也不丢任务。
        logger.warning("DeferredDbTaskRunner %s saturated; running inline", self._name)
        await self._run_job(job)

    async def _worker(self, queue: asyncio.Queue[JobFactory]) -> None:
        while True:
            job = await queue.get()
            try:
                await self._run_job(job)
            finally:
                queue.task_done()

    async def _run_job(self, job: JobFactory) -> None:
        try:
            await job()
        except Exception:
            logger.exception("Deferred task failed name=%s", self._name)

    async def shutdown(self) -> None:
        """优雅关停：等 worker 把在途与排队任务跑完（限时），再取消空闲 worker。

        ``queue.join`` 在所有入队任务 ``task_done`` 后返回，故排队任务不丢；
        限时是为避免个别在途任务卡死拖住关停（超时后强制取消，与旧 fire-and-forget 行为一致）。
        """
        queue = self._queue
        workers = [w for w in self._workers if not w.done()]
        if queue is not None and workers:
            with suppress(asyncio.TimeoutError):
                await asyncio.wait_for(queue.join(), self._shutdown_drain_timeout_seconds)
        for worker in workers:
            worker.cancel()
        if workers:
            await asyncio.gather(*workers, return_exceptions=True)
        self._workers = []
        self._queue = None
        self._loop = None


__all__ = ["DeferredDbTaskRunner", "JobFactory"]
