from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

from domains.gateway.application.pricing.litellm_upstream_price_sync import (
    LitellmUpstreamPriceSyncService,
)


class FakeUpstreamPricingRepository:
    def __init__(self) -> None:
        self.created: list[dict[str, object]] = []

    async def get_active(self, **_kwargs: object):
        return None

    async def create(self, **kwargs: object):
        self.created.append(kwargs)
        return SimpleNamespace(**kwargs)

    async def close_effective(self, _row: object, **_kwargs: object) -> None:
        return None


@pytest.mark.asyncio
async def test_litellm_sync_filters_to_allowed_providers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(
        __import__("sys").modules,
        "litellm",
        SimpleNamespace(
            model_cost={
                "openai/gpt-4o-mini": {
                    "input_cost_per_token": 0.00000015,
                    "output_cost_per_token": 0.0000006,
                },
                "vertex_ai/gemini-1.5-pro": {
                    "input_cost_per_token": 0.00000125,
                    "output_cost_per_token": 0.000005,
                },
                "anthropic/claude-3-haiku-20240307": {
                    "input_cost_per_token": 0.00000025,
                    "output_cost_per_token": 0.00000125,
                },
            }
        ),
    )
    repo = FakeUpstreamPricingRepository()

    report = await LitellmUpstreamPriceSyncService(repo).sync_from_litellm_model_cost(
        allowed_providers={"openai"},
        gateway_models=[("vertex_ai", "vertex_ai/gemini-1.5-pro", "chat")],
    )

    assert report.created == 1
    assert report.updated == 0
    assert report.skipped_manual == 0
    assert [row["provider"] for row in repo.created] == ["openai"]
    assert repo.created[0]["input_cost_per_token"] == Decimal("1.5E-7")
