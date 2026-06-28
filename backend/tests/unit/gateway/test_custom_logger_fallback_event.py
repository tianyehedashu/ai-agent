"""GatewayCustomLogger fallback 事件钩子：回填 metadata.gateway_fallback_chain。"""

from __future__ import annotations

import uuid

import pytest

from domains.gateway.domain.route.router_model_name import encode_router_model_name
from domains.gateway.infrastructure.callbacks.custom_logger import get_logger_singleton

_TEAM = uuid.uuid4()


@pytest.mark.asyncio
async def test_success_fallback_event_records_chain() -> None:
    logger = get_logger_singleton()
    metadata: dict[str, object] = {"gateway_route_name": "smart-route"}
    kwargs = {
        "model": encode_router_model_name(_TEAM, "backup-route"),
        "metadata": metadata,
        "litellm_params": {"model_info": {"gateway_real_model": "claude-3-5-sonnet"}},
    }
    await logger.log_success_fallback_event(
        original_model_group=encode_router_model_name(_TEAM, "smart-route"),
        kwargs=kwargs,
        original_exception=RuntimeError("primary failed"),
    )
    assert metadata["gateway_fallback_chain"] == ["smart-route", "claude-3-5-sonnet"]


@pytest.mark.asyncio
async def test_failure_fallback_event_records_chain_without_metadata_key() -> None:
    logger = get_logger_singleton()
    kwargs: dict[str, object] = {"model": "final-route"}
    await logger.log_failure_fallback_event(
        original_model_group="smart-route",
        kwargs=kwargs,
        original_exception=RuntimeError("all failed"),
    )
    metadata = kwargs["metadata"]
    assert isinstance(metadata, dict)
    assert metadata["gateway_fallback_chain"] == ["smart-route", "final-route"]
