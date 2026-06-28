"""测试 _collect_ttfb_stream 流式 TTFB 采集。"""

from __future__ import annotations

import time
from typing import Any

import pytest

from domains.gateway.application.proxy.proxy_chat_entries import _collect_ttfb_stream


class _FakeAsyncGenerator:
    """模拟异步生成器，支持延时可控的 yield。"""

    def __init__(self, delay_seconds: float = 0.01, chunk_count: int = 3) -> None:
        self._delay = delay_seconds
        self._count = chunk_count

    def __aiter__(self) -> _FakeAsyncGenerator:
        return self

    async def __anext__(self) -> str:
        if self._count <= 0:
            raise StopAsyncIteration
        self._count -= 1
        await _sleep(self._delay)
        return f"chunk-{self._count}"


async def _sleep(seconds: float) -> None:
    import asyncio

    await asyncio.sleep(seconds)


async def _collect_all(stream: Any) -> list[Any]:
    return [chunk async for chunk in stream]


@pytest.mark.asyncio
async def test_ttfb_written_on_first_chunk() -> None:
    """首 chunk 到达时 metadata 中应写入 gateway_ttfb_ms。"""
    metadata: dict[str, Any] = {}
    started = time.perf_counter()
    # 每个 chunk 先 sleep 20ms
    wrapped = _collect_ttfb_stream(_FakeAsyncGenerator(0.02, 2), metadata, started)
    chunks = await _collect_all(wrapped)

    assert len(chunks) == 2
    assert "gateway_ttfb_ms" in metadata
    assert isinstance(metadata["gateway_ttfb_ms"], int)
    assert metadata["gateway_ttfb_ms"] >= 0
    # TTFB 不应超过总体耗时太多（allow generous tolerance）
    elapsed = int((time.perf_counter() - started) * 1000)
    assert metadata["gateway_ttfb_ms"] <= elapsed + 50


@pytest.mark.asyncio
async def test_ttfb_not_overwritten_on_later_chunks() -> None:
    """后续 chunk 不应覆盖首 chunk 记录的 TTFB 值。"""
    metadata: dict[str, Any] = {}
    started = time.perf_counter()
    wrapped = _collect_ttfb_stream(_FakeAsyncGenerator(0.01, 5), metadata, started)
    chunks = await _collect_all(wrapped)

    first_ttfb = metadata["gateway_ttfb_ms"]
    assert len(chunks) == 5
    assert metadata["gateway_ttfb_ms"] == first_ttfb


@pytest.mark.asyncio
async def test_empty_stream_no_keys() -> None:
    """空流不应写入任何值到 metadata。"""
    metadata: dict[str, Any] = {}
    started = time.perf_counter()
    wrapped = _collect_ttfb_stream(_FakeAsyncGenerator(0.01, 0), metadata, started)
    chunks = await _collect_all(wrapped)

    assert len(chunks) == 0
    assert "gateway_ttfb_ms" not in metadata


@pytest.mark.asyncio
async def test_existing_metadata_keys_preserved() -> None:
    """metadata 中已有其他键不受影响。"""
    metadata: dict[str, Any] = {"gateway_team_id": "t-1", "gateway_user_id": "u-2"}
    started = time.perf_counter()
    wrapped = _collect_ttfb_stream(_FakeAsyncGenerator(0.01, 1), metadata, started)
    chunks = await _collect_all(wrapped)

    assert len(chunks) == 1
    assert metadata["gateway_team_id"] == "t-1"
    assert metadata["gateway_user_id"] == "u-2"
    assert "gateway_ttfb_ms" in metadata
