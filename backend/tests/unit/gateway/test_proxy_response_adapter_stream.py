"""proxy_response_adapter 流式响应单元测试。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from decimal import Decimal
from typing import Any
import uuid

from unittest.mock import AsyncMock

import pytest

from domains.gateway.application.proxy_response_adapter import adapt_stream
from domains.gateway.application.proxy_use_case import ProxyContext
from domains.gateway.domain.types import GatewayCapability, VirtualKeyPrincipal


def _vkey(team_id: uuid.UUID) -> VirtualKeyPrincipal:
    return VirtualKeyPrincipal(
        vkey_id=uuid.uuid4(),
        vkey_name="test",
        team_id=team_id,
        user_id=uuid.uuid4(),
        allowed_models=(),
        allowed_capabilities=(),
        rpm_limit=None,
        tpm_limit=None,
        store_full_messages=False,
        guardrail_enabled=False,
        is_system=False,
    )


class _NoopBudget:
    async def check_rate_limit(self, **_kwargs: object) -> None:
        return None

    async def check_budget(self, **_kwargs: object) -> Any:
        from domains.gateway.application.budget_service import BudgetCheckResult

        return BudgetCheckResult(allowed=True)

    async def reserve(self, **_kwargs: object) -> None:
        return None

    async def release(self, **_kwargs: object) -> None:
        return None

    async def commit(self, **_kwargs: object) -> None:
        return None

    async def read_budget_usage_batch(self, _coords: object) -> dict[object, object]:
        return {}


@pytest.mark.asyncio
async def test_adapt_stream_sets_cache_hit_on_last_usage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OpenAI 兼容流式：最后一个 chunk 含 usage 时 metadata 应标记 gateway_cache_hit。"""
    monkeypatch.setattr(
        "domains.gateway.application.proxy_response_adapter.commit_cached_platform_budgets",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "domains.gateway.application.proxy_response_adapter.schedule_settle_usage",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "domains.gateway.application.proxy_response_adapter._calc_upstream_cost",
        lambda *args, **kwargs: Decimal("0"),
    )
    monkeypatch.setattr(
        "domains.gateway.application.pricing.pricing_budget_cost.proxy_budget_cost_usd",
        lambda *args, **kwargs: Decimal("0"),
    )
    monkeypatch.setattr(
        "domains.gateway.application.pricing.pricing_display_cost.resolve_downstream_display_cost_usd",
        lambda *args, **kwargs: Decimal("0"),
    )

    async def fake_stream() -> AsyncIterator[dict[str, Any]]:
        yield {"choices": [{"delta": {"content": "h"}}]}
        yield {
            "choices": [{"delta": {}}],
            "usage": {"total_tokens": 10, "prompt_tokens_details": {"cached_tokens": 8}},
        }

    team_id = uuid.uuid4()
    ctx = ProxyContext(
        team_id=team_id,
        user_id=uuid.uuid4(),
        vkey=_vkey(team_id),
        capability=GatewayCapability.CHAT,
        request_id="req-stream-cache",
        store_full_messages=False,
        guardrail_enabled=False,
    )
    metadata: dict[str, Any] = {}
    stream = adapt_stream(
        fake_stream(),
        ctx,
        _NoopBudget(),
        metadata=metadata,
        downstream_custom=None,
    )
    chunks = [chunk async for chunk in stream]
    assert len(chunks) == 2
    assert metadata.get("gateway_cache_hit") is True


@pytest.mark.asyncio
async def test_adapt_stream_no_cache_hit_when_usage_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OpenAI 兼容流式：chunk 不含缓存 usage 时 gateway_cache_hit 不应为 True。"""
    monkeypatch.setattr(
        "domains.gateway.application.proxy_response_adapter.commit_cached_platform_budgets",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "domains.gateway.application.proxy_response_adapter.schedule_settle_usage",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "domains.gateway.application.proxy_response_adapter._calc_upstream_cost",
        lambda *args, **kwargs: Decimal("0"),
    )
    monkeypatch.setattr(
        "domains.gateway.application.pricing.pricing_budget_cost.proxy_budget_cost_usd",
        lambda *args, **kwargs: Decimal("0"),
    )
    monkeypatch.setattr(
        "domains.gateway.application.pricing.pricing_display_cost.resolve_downstream_display_cost_usd",
        lambda *args, **kwargs: Decimal("0"),
    )

    async def fake_stream() -> AsyncIterator[dict[str, Any]]:
        yield {"choices": [{"delta": {"content": "h"}}]}
        yield {"choices": [{"delta": {}}], "usage": {"total_tokens": 10}}

    team_id = uuid.uuid4()
    ctx = ProxyContext(
        team_id=team_id,
        user_id=uuid.uuid4(),
        vkey=_vkey(team_id),
        capability=GatewayCapability.CHAT,
        request_id="req-stream-no-cache",
        store_full_messages=False,
        guardrail_enabled=False,
    )
    metadata: dict[str, Any] = {}
    stream = adapt_stream(
        fake_stream(),
        ctx,
        _NoopBudget(),
        metadata=metadata,
        downstream_custom=None,
    )
    chunks = [chunk async for chunk in stream]
    assert len(chunks) == 2
    assert metadata.get("gateway_cache_hit") is not True
