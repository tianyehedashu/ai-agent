"""代理侧后台任务登记。

非流式响应后的结算采用 fire-and-forget；统一登记便于应用关闭和测试 fixture 收口。
"""

from __future__ import annotations

import asyncio
from typing import Any

_proxy_deferred_tasks: set[asyncio.Task[Any]] = set()


def register_proxy_deferred_task(task: asyncio.Task[Any]) -> None:
    """登记须在进程/测试 teardown 时取消并等待的代理后台任务。"""
    _proxy_deferred_tasks.add(task)

    def _done(t: asyncio.Task[Any]) -> None:
        _proxy_deferred_tasks.discard(t)

    task.add_done_callback(_done)


async def shutdown_proxy_deferred_tasks() -> None:
    """收口代理延迟任务：先排空有界执行器（剩余结算任务会记入合并 flusher），
    再取消并等待已登记的 flusher / 一次性刷写任务（取消触发其 finally 排空）。
    """
    from domains.gateway.application.observability.deferred_task_runner import proxy_deferred_runner

    await proxy_deferred_runner.shutdown()
    pending = [t for t in list(_proxy_deferred_tasks) if not t.done()]
    for task in pending:
        task.cancel()
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)


__all__ = ["register_proxy_deferred_task", "shutdown_proxy_deferred_tasks"]
