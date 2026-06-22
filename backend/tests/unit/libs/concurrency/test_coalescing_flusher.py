"""CoalescingFlusher 合并 / 刷写 / 失败并回单测。"""

from __future__ import annotations

import asyncio
from contextlib import suppress

import pytest

from libs.concurrency import CoalescingFlusher


def _add_merge(existing: int, new: int) -> int:
    return existing + new


@pytest.mark.asyncio
async def test_add_coalesces_then_flush_batches() -> None:
    captured: list[list[tuple[str, int]]] = []

    async def flush(entries: list[tuple[str, int]]) -> None:
        captured.append(entries)

    flusher: CoalescingFlusher[str, int] = CoalescingFlusher(
        name="t",
        merge=_add_merge,
        flush=flush,
        interval_seconds=lambda: 3600.0,
        max_pending=lambda: 1000,
    )
    flusher.add("a", 1)
    flusher.add("a", 2)
    flusher.add("b", 5)
    assert flusher._pending == {"a": 3, "b": 5}

    await flusher._flush()

    assert captured == [[("a", 3), ("b", 5)]]
    assert flusher._pending == {}

    if flusher._flusher is not None:
        flusher._flusher.cancel()
        with suppress(asyncio.CancelledError):
            await flusher._flusher


@pytest.mark.asyncio
async def test_flush_failure_merges_back_for_retry() -> None:
    calls = {"n": 0}

    async def flush(entries: list[tuple[str, int]]) -> None:
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("db down")

    flusher: CoalescingFlusher[str, int] = CoalescingFlusher(
        name="t",
        merge=_add_merge,
        flush=flush,
        interval_seconds=lambda: 3600.0,
        max_pending=lambda: 1000,
    )
    flusher.add("a", 4)
    await flusher._flush()  # 第一次失败 → 并回
    assert flusher._pending == {"a": 4}

    flusher.add("a", 1)  # 新增量叠加在并回值上
    await flusher._flush()  # 第二次成功
    assert flusher._pending == {}

    if flusher._flusher is not None:
        flusher._flusher.cancel()
        with suppress(asyncio.CancelledError):
            await flusher._flusher


@pytest.mark.asyncio
async def test_register_task_receives_lazy_started_flusher() -> None:
    registered: list[asyncio.Task[None]] = []

    async def flush(entries: list[tuple[str, int]]) -> None:
        return None

    flusher: CoalescingFlusher[str, int] = CoalescingFlusher(
        name="t",
        merge=_add_merge,
        flush=flush,
        interval_seconds=lambda: 3600.0,
        max_pending=lambda: 1000,
        register_task=registered.append,
    )
    flusher.add("a", 1)
    assert flusher._flusher is not None
    assert flusher._flusher in registered

    flusher._flusher.cancel()
    with suppress(asyncio.CancelledError):
        await flusher._flusher
