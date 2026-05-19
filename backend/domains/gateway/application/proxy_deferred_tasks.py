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
    """取消并等待所有已登记的代理延迟任务。"""
    pending = [t for t in list(_proxy_deferred_tasks) if not t.done()]
    for task in pending:
        task.cancel()
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)


__all__ = ["register_proxy_deferred_task", "shutdown_proxy_deferred_tasks"]
