"""``PricingService.sync_to_litellm_registry`` 增量与去重行为单测。"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from domains.gateway.application.pricing.pricing_service import (
    PricingService,
    reset_litellm_pricing_register_cache,
)


def _row(
    upstream_model: str,
    *,
    inp: str = "1e-6",
    out: str = "2e-6",
    version: int = 1,
    extra: dict | None = None,
):
    return SimpleNamespace(
        upstream_model=upstream_model,
        input_cost_per_token=Decimal(inp),
        output_cost_per_token=Decimal(out),
        cache_creation_input_token_cost=None,
        cache_read_input_token_cost=None,
        extra=extra,
        version=version,
    )


def _make_service(
    rows: list,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[PricingService, list[dict]]:
    upstream = SimpleNamespace(list_active=AsyncMock(return_value=rows))
    captured: list[dict] = []

    def _capture_register_model(*args: object, **kwargs: object) -> None:
        if args:
            captured.append(dict(args[0]))  # type: ignore[arg-type]
        elif "model_cost" in kwargs:
            captured.append(dict(kwargs["model_cost"]))  # type: ignore[arg-type]

    monkeypatch.setattr("litellm.register_model", _capture_register_model)

    svc = PricingService(upstream, SimpleNamespace())  # type: ignore[arg-type]
    return svc, captured


@pytest.mark.asyncio
async def test_sync_skips_unchanged_fingerprints(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_litellm_pricing_register_cache()
    rows = [_row("openai/gpt-4o"), _row("anthropic/claude-3-5-sonnet")]
    svc, captured = _make_service(rows, monkeypatch)

    first = await svc.sync_to_litellm_registry()
    second = await svc.sync_to_litellm_registry()

    assert first == 2
    assert second == 0, "未变更行不应重复 register"
    assert len(captured) == 1
    assert set(captured[0].keys()) == {"openai/gpt-4o", "anthropic/claude-3-5-sonnet"}


@pytest.mark.asyncio
async def test_sync_only_keys_filters_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_litellm_pricing_register_cache()
    rows = [_row("openai/gpt-4o"), _row("anthropic/claude-3-5-sonnet")]
    svc, captured = _make_service(rows, monkeypatch)

    written = await svc.sync_to_litellm_registry(only_keys={"openai/gpt-4o"})

    assert written == 1
    assert captured == [
        {
            "openai/gpt-4o": {
                "input_cost_per_token": 1e-6,
                "output_cost_per_token": 2e-6,
            }
        }
    ]


@pytest.mark.asyncio
async def test_sync_detects_version_bump(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_litellm_pricing_register_cache()
    rows = [_row("openai/gpt-4o", version=1)]
    svc, captured = _make_service(rows, monkeypatch)
    await svc.sync_to_litellm_registry()

    rows[0] = _row("openai/gpt-4o", inp="9e-7", version=2)
    svc, captured2 = _make_service(rows, monkeypatch)
    written = await svc.sync_to_litellm_registry()

    assert written == 1
    assert captured2 and captured2[0]["openai/gpt-4o"]["input_cost_per_token"] == 9e-7


@pytest.mark.asyncio
async def test_sync_only_keys_empty_set_is_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_litellm_pricing_register_cache()
    svc, captured = _make_service([_row("openai/gpt-4o")], monkeypatch)
    written = await svc.sync_to_litellm_registry(only_keys=set())
    assert written == 0
    assert captured == []
