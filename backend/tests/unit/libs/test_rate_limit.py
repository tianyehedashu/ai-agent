"""libs.rate_limit 单测"""

from __future__ import annotations

from unittest.mock import AsyncMock
import uuid

from fastapi import status
from fastapi.exceptions import HTTPException
import pytest

from libs.rate_limit import check_fixed_window_rate_limit, check_probe_rate_limit


@pytest.mark.asyncio
async def test_probe_rate_limit_allows_first_request(monkeypatch) -> None:
    fake_client = AsyncMock()
    fake_client.set.return_value = True
    monkeypatch.setattr("libs.rate_limit.get_redis_client", AsyncMock(return_value=fake_client))

    user_id = uuid.uuid4()
    model_id = uuid.uuid4()
    await check_probe_rate_limit(user_id, model_id)

    fake_client.set.assert_awaited_once_with(
        f"gateway:probe:limit:{user_id}:{model_id}", "1", nx=True, ex=60
    )


@pytest.mark.asyncio
async def test_probe_rate_limit_rejects_second_request(monkeypatch) -> None:
    fake_client = AsyncMock()
    fake_client.set.return_value = None
    monkeypatch.setattr("libs.rate_limit.get_redis_client", AsyncMock(return_value=fake_client))

    user_id = uuid.uuid4()
    model_id = uuid.uuid4()
    with pytest.raises(HTTPException) as exc_info:
        await check_probe_rate_limit(user_id, model_id)

    assert exc_info.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert "Retry-After" in exc_info.value.headers
    assert exc_info.value.headers["Retry-After"] == "60"


@pytest.mark.asyncio
async def test_fixed_window_rate_limit_allows_under_quota(monkeypatch) -> None:
    fake_client = AsyncMock()
    fake_client.incr.return_value = 2
    monkeypatch.setattr("libs.rate_limit.get_redis_client", AsyncMock(return_value=fake_client))

    await check_fixed_window_rate_limit(
        key="test:limit:1",
        window_seconds=60,
        max_requests=3,
    )

    fake_client.incr.assert_awaited_once_with("test:limit:1")
    fake_client.expire.assert_not_awaited()


@pytest.mark.asyncio
async def test_fixed_window_rate_limit_sets_expire_on_first_request(monkeypatch) -> None:
    fake_client = AsyncMock()
    fake_client.incr.return_value = 1
    monkeypatch.setattr("libs.rate_limit.get_redis_client", AsyncMock(return_value=fake_client))

    await check_fixed_window_rate_limit(
        key="test:limit:1",
        window_seconds=60,
        max_requests=3,
    )

    fake_client.incr.assert_awaited_once_with("test:limit:1")
    fake_client.expire.assert_awaited_once_with("test:limit:1", 60)


@pytest.mark.asyncio
async def test_fixed_window_rate_limit_rejects_over_quota(monkeypatch) -> None:
    fake_client = AsyncMock()
    fake_client.incr.return_value = 4
    monkeypatch.setattr("libs.rate_limit.get_redis_client", AsyncMock(return_value=fake_client))

    with pytest.raises(HTTPException) as exc_info:
        await check_fixed_window_rate_limit(
            key="test:limit:1",
            window_seconds=60,
            max_requests=3,
        )

    assert exc_info.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS
