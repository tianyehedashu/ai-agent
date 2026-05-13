"""background_tasks 单元测试"""

import asyncio

from fastapi import FastAPI
import pytest

from libs.background_tasks import (
    init_background_tasks,
    register_app_background_task,
    shutdown_app_background_tasks,
)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_shutdown_cancels_registered_task() -> None:
    app = FastAPI()
    init_background_tasks(app)
    gate = asyncio.Event()

    async def blocked() -> None:
        gate.set()
        await asyncio.sleep(3600)

    task = asyncio.create_task(blocked())
    register_app_background_task(app, task)
    await asyncio.wait_for(gate.wait(), timeout=2.0)
    await shutdown_app_background_tasks(app)
    assert task.cancelled()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_completed_task_removed_from_set() -> None:
    app = FastAPI()
    init_background_tasks(app)

    async def done_quick() -> None:
        return None

    task = asyncio.create_task(done_quick())
    register_app_background_task(app, task)
    await task
    # done_callback 在事件循环下一轮可能尚未执行，短等
    for _ in range(50):
        if not app.state.background_tasks:
            break
        await asyncio.sleep(0)
    assert len(app.state.background_tasks) == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_shutdown_proxy_deferred_tasks() -> None:
    from domains.gateway.application.proxy_use_case import (
        register_proxy_deferred_task,
        shutdown_proxy_deferred_tasks,
    )

    gate = asyncio.Event()

    async def long_running() -> None:
        gate.set()
        await asyncio.sleep(3600)

    task = asyncio.create_task(long_running())
    register_proxy_deferred_task(task)
    await asyncio.wait_for(gate.wait(), timeout=2.0)
    await shutdown_proxy_deferred_tasks()
    assert task.cancelled()
