"""custom_logger：SLO (StandardLoggingPayload) 补充 cache_hit / cached_tokens。

当 provider（如 Volcengine DeepSeek、ZhipuAI GLM）在 response_obj.usage 中
不返回 prompt_tokens_details 时，LiteLLM SLO 仍可能包含 cache_hit 和
cache_read_input_tokens。_persist_event 应从 SLO 回退读取。
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from domains.gateway.infrastructure.callbacks.custom_logger import _persist_event


@pytest.mark.asyncio
async def test_persist_event_slo_cache_hit_fallback() -> None:
    """response_obj.usage 无 prompt_tokens_details 但 SLO 有 cache_hit → 应写入 cache_hit=True。"""

    captured_insert: dict[str, Any] = {}

    class FakeRepo:
        def __init__(self, _session: Any) -> None:
            pass

        async def insert(self, **kwargs: Any) -> None:
            captured_insert.update(kwargs)

    response_obj = SimpleNamespace(
        usage={"prompt_tokens": 5000, "completion_tokens": 200},
    )

    kwargs: dict[str, Any] = {
        "model": "deepseek-v4-pro-chat",
        "metadata": {
            "gateway_team_id": "00000000-0000-0000-0000-000000000001",
            "gateway_user_id": "00000000-0000-0000-0000-000000000002",
            "gateway_capability": "chat",
        },
        "standard_logging_object": {
            "cache_hit": True,
            "cache_read_input_tokens": 3000,
            "response_cost": 0.001,
        },
    }

    with (
        patch(
            "domains.gateway.infrastructure.repositories.request_log_repository.RequestLogRepository",
            FakeRepo,
        ),
        patch(
            "domains.gateway.infrastructure.callbacks.custom_logger.get_session_context",
        ) as mock_ctx,
        patch(
            "domains.gateway.infrastructure.callbacks.custom_logger._calc_cost",
            return_value=(Decimal("0.001"), "litellm_slo"),
        ),
        patch(
            "domains.gateway.infrastructure.callbacks.custom_logger._credential_snapshots_for_persist",
            return_value=(None, None),
        ),
        patch(
            "domains.gateway.infrastructure.callbacks.custom_logger._deployment_from_model_info_kwargs",
            return_value=(None, None),
        ),
        patch(
            "domains.gateway.infrastructure.callbacks.custom_logger.gateway_provider_for_persist",
            return_value="volcengine",
        ),
        patch(
            "domains.gateway.infrastructure.callbacks.custom_logger._resolve_persist_user_id",
            return_value=None,
        ),
        patch(
            "domains.gateway.infrastructure.callbacks.custom_logger.should_persist_request_log_row",
            return_value=True,
        ),
        patch(
            "domains.gateway.infrastructure.callbacks.custom_logger.get_redis_client",
            return_value=None,
        ),
    ):
        session_mock = AsyncMock()
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=session_mock)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

        await _persist_event(
            kwargs=kwargs,
            response_obj=response_obj,
            start_time=datetime(2026, 6, 2, 10, 0, tzinfo=UTC),
            end_time=datetime(2026, 6, 2, 10, 0, 5, tzinfo=UTC),
            status="success",
            error_code=None,
            error_message=None,
        )

    assert captured_insert.get("cache_hit") is True
    assert captured_insert.get("cached_tokens") == 3000


@pytest.mark.asyncio
async def test_persist_event_no_slo_cache_remains_false() -> None:
    """SLO 无 cache_hit 且 response_obj.usage 无缓存 → cache_hit 应为 False。"""

    captured_insert: dict[str, Any] = {}

    class FakeRepo:
        def __init__(self, _session: Any) -> None:
            pass

        async def insert(self, **kwargs: Any) -> None:
            captured_insert.update(kwargs)

    response_obj = SimpleNamespace(
        usage={"prompt_tokens": 100, "completion_tokens": 50},
    )

    kwargs: dict[str, Any] = {
        "model": "glm-5.1",
        "metadata": {
            "gateway_team_id": "00000000-0000-0000-0000-000000000001",
            "gateway_capability": "chat",
        },
        "standard_logging_object": {
            "response_cost": 0.0,
        },
    }

    with (
        patch(
            "domains.gateway.infrastructure.repositories.request_log_repository.RequestLogRepository",
            FakeRepo,
        ),
        patch(
            "domains.gateway.infrastructure.callbacks.custom_logger.get_session_context",
        ) as mock_ctx,
        patch(
            "domains.gateway.infrastructure.callbacks.custom_logger._calc_cost",
            return_value=(Decimal("0"), "zero"),
        ),
        patch(
            "domains.gateway.infrastructure.callbacks.custom_logger._credential_snapshots_for_persist",
            return_value=(None, None),
        ),
        patch(
            "domains.gateway.infrastructure.callbacks.custom_logger._deployment_from_model_info_kwargs",
            return_value=(None, None),
        ),
        patch(
            "domains.gateway.infrastructure.callbacks.custom_logger.gateway_provider_for_persist",
            return_value="zhipuai",
        ),
        patch(
            "domains.gateway.infrastructure.callbacks.custom_logger._resolve_persist_user_id",
            return_value=None,
        ),
        patch(
            "domains.gateway.infrastructure.callbacks.custom_logger.should_persist_request_log_row",
            return_value=True,
        ),
        patch(
            "domains.gateway.infrastructure.callbacks.custom_logger.get_redis_client",
            return_value=None,
        ),
    ):
        session_mock = AsyncMock()
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=session_mock)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

        await _persist_event(
            kwargs=kwargs,
            response_obj=response_obj,
            start_time=datetime(2026, 6, 2, 10, 0, tzinfo=UTC),
            end_time=datetime(2026, 6, 2, 10, 0, 1, tzinfo=UTC),
            status="success",
            error_code=None,
            error_message=None,
        )

    assert captured_insert.get("cache_hit") is False
    assert captured_insert.get("cached_tokens") == 0


@pytest.mark.asyncio
async def test_persist_event_slo_cache_creation_fallback() -> None:
    """当 SLO 包含 cache_creation_input_tokens 且 response usage 提取失败时，应补齐 input_tokens。"""

    captured_insert: dict[str, Any] = {}

    class FakeRepo:
        def __init__(self, _session: Any) -> None:
            pass

        async def insert(self, **kwargs: Any) -> None:
            captured_insert.update(kwargs)

    # response_obj.usage 无 prompt_tokens 也无 cache 信息，模拟提取失败
    response_obj = SimpleNamespace(usage={})

    kwargs: dict[str, Any] = {
        "model": "some-anthropic-model",
        "metadata": {
            "gateway_team_id": "00000000-0000-0000-0000-000000000001",
            "gateway_user_id": "00000000-0000-0000-0000-000000000002",
            "gateway_capability": "chat",
        },
        "standard_logging_object": {
            "cache_hit": True,
            "cache_read_input_tokens": 4000,
            "cache_creation_input_tokens": 500,
            "response_cost": 0.002,
        },
    }

    with (
        patch(
            "domains.gateway.infrastructure.repositories.request_log_repository.RequestLogRepository",
            FakeRepo,
        ),
        patch(
            "domains.gateway.infrastructure.callbacks.custom_logger.get_session_context",
        ) as mock_ctx,
        patch(
            "domains.gateway.infrastructure.callbacks.custom_logger._calc_cost",
            return_value=(Decimal("0.002"), "litellm_slo"),
        ),
        patch(
            "domains.gateway.infrastructure.callbacks.custom_logger._credential_snapshots_for_persist",
            return_value=(None, None),
        ),
        patch(
            "domains.gateway.infrastructure.callbacks.custom_logger._deployment_from_model_info_kwargs",
            return_value=(None, None),
        ),
        patch(
            "domains.gateway.infrastructure.callbacks.custom_logger.gateway_provider_for_persist",
            return_value="anthropic",
        ),
        patch(
            "domains.gateway.infrastructure.callbacks.custom_logger._resolve_persist_user_id",
            return_value=None,
        ),
        patch(
            "domains.gateway.infrastructure.callbacks.custom_logger.should_persist_request_log_row",
            return_value=True,
        ),
        patch(
            "domains.gateway.infrastructure.callbacks.custom_logger.get_redis_client",
            return_value=None,
        ),
    ):
        session_mock = AsyncMock()
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=session_mock)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

        await _persist_event(
            kwargs=kwargs,
            response_obj=response_obj,
            start_time=datetime(2026, 6, 2, 10, 0, tzinfo=UTC),
            end_time=datetime(2026, 6, 2, 10, 0, 3, tzinfo=UTC),
            status="success",
            error_code=None,
            error_message=None,
        )

    assert captured_insert.get("cache_hit") is True
    assert captured_insert.get("cached_tokens") == 4000  # cache_read only
    # input_tokens 从 SLO 补齐：cache_read(4000) + cache_creation(500)
    assert captured_insert.get("input_tokens") == 4500
