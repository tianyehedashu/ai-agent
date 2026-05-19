"""proxy_stream_settlement 流末结算单测。"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, patch
import uuid

import pytest

from domains.gateway.application.proxy_stream_settlement import (
    finalize_deferred_stream_settlement,
    resolve_stream_budget_cost_usd,
    stream_usage_token_total,
)
from domains.gateway.application.proxy_use_case import ProxyContext
from domains.gateway.domain.types import GatewayCapability


def test_stream_usage_token_total_openai() -> None:
    assert stream_usage_token_total({"total_tokens": 42}) == 42


def test_stream_usage_token_total_anthropic() -> None:
    usage = {
        "input_tokens": 10,
        "output_tokens": 5,
        "cache_read_input_tokens": 2,
    }
    # 预算 token 计数与 anthropic_usage_total_tokens 一致（不含 cache 重复计）
    assert stream_usage_token_total(usage) == 15


def test_resolve_stream_budget_cost_uses_metadata_rate() -> None:
    metadata = {
        "gateway_pricing_upstream": {
            "input_cost_per_token": 0.000003,
            "output_cost_per_token": 0.000015,
        },
    }
    cost = resolve_stream_budget_cost_usd(
        {"input_tokens": 1000, "output_tokens": 500},
        metadata=metadata,
        model="claude-test",
    )
    assert cost > Decimal("0")


@pytest.mark.asyncio
async def test_finalize_deferred_stream_calls_callback_when_cost_positive() -> None:
    team_id = uuid.uuid4()
    ctx = ProxyContext(
        team_id=team_id,
        user_id=uuid.uuid4(),
        vkey=None,
        capability=GatewayCapability.CHAT,
        request_id="req-stream-settle",
        store_full_messages=False,
        guardrail_enabled=False,
        budget_model="m",
    )
    metadata = {
        "gateway_team_id": str(team_id),
        "gateway_defer_cost_settlement": True,
        "gateway_pricing_upstream": {
            "input_cost_per_token": 0.000003,
            "output_cost_per_token": 0.000015,
        },
    }
    mock_commit = AsyncMock()
    mock_settle = AsyncMock()
    with (
        patch(
            "domains.gateway.application.budget_callback_settlement.commit_budget_from_callback",
            mock_commit,
        ),
        patch(
            "domains.gateway.application.proxy_use_case._settle_usage",
            mock_settle,
        ),
    ):
        await finalize_deferred_stream_settlement(
            ctx,
            AsyncMock(),
            metadata,
            {"input_tokens": 100, "output_tokens": 50},
            None,
        )
    mock_commit.assert_awaited_once()
    assert mock_commit.await_args.kwargs["cost_usd"] > Decimal("0")
    mock_settle.assert_awaited_once()
    assert mock_settle.await_args.kwargs["cost"] == Decimal("0")
