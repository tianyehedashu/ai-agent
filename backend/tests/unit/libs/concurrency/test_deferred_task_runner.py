"""DeferredDbTaskRunner 并发 / 背压降级 / 关停排空单测。"""

from __future__ import annotations

import asyncio

import pytest

from libs.concurrency import DeferredDbTaskRunner


@pytest.mark.asyncio
async def test_workers_process_submitted_jobs() -> None:
    done: list[int] = []

    def make(n: int):
        async def job() -> None:
            done.append(n)

        return job

    runner = DeferredDbTaskRunner(
        name="t",
        max_workers=lambda: 3,
        max_queue=lambda: 100,
        submit_block_timeout_seconds=lambda: 0.5,
    )
    for i in range(10):
        await runner.submit(make(i))
    await runner.shutdown()
    assert sorted(done) == list(range(10))


@pytest.mark.asyncio
async def test_saturation_runs_inline_without_dropping() -> None:
    started = asyncio.Event()
    gate = asyncio.Event()
    order: list[str] = []

    async def blocking() -> None:
        order.append("block-start")
        started.set()
        await gate.wait()
        order.append("block-end")

    async def queued() -> None:
        order.append("queued")

    async def overflow() -> None:
        order.append("overflow")

    runner = DeferredDbTaskRunner(
        name="t",
        max_workers=lambda: 1,
        max_queue=lambda: 1,
        submit_block_timeout_seconds=lambda: 0.0,
    )
    await runner.submit(lambda: blocking())
    await asyncio.wait_for(started.wait(), timeout=1.0)
    await runner.submit(lambda: queued())  # 占满有界队列（容量 1）
    await runner.submit(lambda: overflow())  # 队列满 + 超时 0 → inline 立即执行

    assert "overflow" in order
    assert "queued" not in order  # 仍排队，唯一 worker 仍被 blocking 占用

    gate.set()
    await runner.shutdown()  # 排空队列：queued 不丢
    assert "queued" in order
    assert "block-end" in order
