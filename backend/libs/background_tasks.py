"""
应用级后台 asyncio 任务注册，供进程关闭时统一取消并等待结束。
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any


def init_background_tasks(app: Any) -> None:
    """在应用启动时初始化任务集合（幂等）。"""
    if getattr(app.state, "background_tasks", None) is None:
        app.state.background_tasks = set()


def register_app_background_task(app: Any, task: asyncio.Task[Any]) -> None:
    """登记后台任务；完成后自动从集合移除。"""
    init_background_tasks(app)
    app.state.background_tasks.add(task)

    def _done(t: asyncio.Task[Any]) -> None:
        with contextlib.suppress(Exception):
            app.state.background_tasks.discard(t)

    task.add_done_callback(_done)


async def shutdown_app_background_tasks(app: Any) -> None:
    """取消并等待所有已登记任务（吞掉取消带来的异常）。"""
    raw = getattr(app.state, "background_tasks", None)
    if not raw:
        return
    tasks: set[asyncio.Task[Any]] = set(raw)
    for t in tasks:
        t.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
