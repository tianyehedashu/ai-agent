"""LiteLLMRouterDeploymentCooldownAdapter 单测。"""

from __future__ import annotations

from unittest.mock import MagicMock
import uuid

import pytest

from domains.gateway.infrastructure.litellm_router_deployment_cooldown_adapter import (
    LiteLLMRouterDeploymentCooldownAdapter,
)


@pytest.fixture
def adapter() -> LiteLLMRouterDeploymentCooldownAdapter:
    return LiteLLMRouterDeploymentCooldownAdapter()


def _make_settings(
    *,
    enabled: bool = True,
    default_seconds: int = 60,
    max_seconds: int = 300,
) -> MagicMock:
    return MagicMock(
        gateway_quota_cooldown_enabled=enabled,
        gateway_quota_cooldown_default_seconds=default_seconds,
        gateway_quota_cooldown_max_seconds=max_seconds,
    )


@pytest.mark.asyncio
async def test_cooldown_delegates_to_router_cooldown_cache(
    monkeypatch,
    adapter: LiteLLMRouterDeploymentCooldownAdapter,
) -> None:
    deployment_id = str(uuid.uuid4())
    cooldown_cache = MagicMock()
    router = MagicMock()
    router.cooldown_cache = cooldown_cache

    monkeypatch.setattr(
        "domains.gateway.infrastructure.litellm_router_deployment_cooldown_adapter.get_router_sync",
        lambda: router,
    )
    monkeypatch.setattr(
        "domains.gateway.infrastructure.litellm_router_deployment_cooldown_adapter.settings",
        _make_settings(default_seconds=90),
    )

    await adapter.cooldown_deployment(
        deployment_id=deployment_id,
        reason="test",
    )

    cooldown_cache.add_deployment_to_cooldown.assert_called_once()
    call_kwargs = cooldown_cache.add_deployment_to_cooldown.call_args.kwargs
    assert call_kwargs["model_id"] == deployment_id
    assert call_kwargs["cooldown_time"] == 90.0
    assert call_kwargs["exception_status"] == 429


@pytest.mark.asyncio
async def test_cooldown_disabled_is_noop(
    monkeypatch,
    adapter: LiteLLMRouterDeploymentCooldownAdapter,
) -> None:
    get_router_spy = MagicMock()
    monkeypatch.setattr(
        "domains.gateway.infrastructure.litellm_router_deployment_cooldown_adapter.settings",
        _make_settings(enabled=False),
    )
    monkeypatch.setattr(
        "domains.gateway.infrastructure.litellm_router_deployment_cooldown_adapter.get_router_sync",
        get_router_spy,
    )

    await adapter.cooldown_deployment(
        deployment_id=str(uuid.uuid4()),
        reason="test",
    )

    get_router_spy.assert_not_called()


@pytest.mark.asyncio
async def test_cooldown_without_router_is_noop(
    monkeypatch,
    adapter: LiteLLMRouterDeploymentCooldownAdapter,
) -> None:
    monkeypatch.setattr(
        "domains.gateway.infrastructure.litellm_router_deployment_cooldown_adapter.get_router_sync",
        lambda: None,
    )
    monkeypatch.setattr(
        "domains.gateway.infrastructure.litellm_router_deployment_cooldown_adapter.settings",
        _make_settings(),
    )

    await adapter.cooldown_deployment(
        deployment_id=str(uuid.uuid4()),
        reason="test",
    )


@pytest.mark.asyncio
async def test_cooldown_without_deployment_id_is_noop(
    monkeypatch,
    adapter: LiteLLMRouterDeploymentCooldownAdapter,
) -> None:
    router = MagicMock()
    monkeypatch.setattr(
        "domains.gateway.infrastructure.litellm_router_deployment_cooldown_adapter.get_router_sync",
        lambda: router,
    )
    monkeypatch.setattr(
        "domains.gateway.infrastructure.litellm_router_deployment_cooldown_adapter.settings",
        _make_settings(),
    )

    await adapter.cooldown_deployment(
        deployment_id="",
        reason="test",
    )

    router.cooldown_cache.add_deployment_to_cooldown.assert_not_called()


@pytest.mark.asyncio
async def test_cooldown_seconds_clamped_to_max(
    monkeypatch,
    adapter: LiteLLMRouterDeploymentCooldownAdapter,
) -> None:
    deployment_id = str(uuid.uuid4())
    cooldown_cache = MagicMock()
    router = MagicMock()
    router.cooldown_cache = cooldown_cache

    monkeypatch.setattr(
        "domains.gateway.infrastructure.litellm_router_deployment_cooldown_adapter.get_router_sync",
        lambda: router,
    )
    monkeypatch.setattr(
        "domains.gateway.infrastructure.litellm_router_deployment_cooldown_adapter.settings",
        _make_settings(default_seconds=60, max_seconds=30),
    )

    await adapter.cooldown_deployment(
        deployment_id=deployment_id,
        reason="test",
    )

    assert cooldown_cache.add_deployment_to_cooldown.call_args.kwargs["cooldown_time"] == 30.0


@pytest.mark.asyncio
async def test_cooldown_default_seconds_zero_is_noop(
    monkeypatch,
    adapter: LiteLLMRouterDeploymentCooldownAdapter,
) -> None:
    router = MagicMock()
    monkeypatch.setattr(
        "domains.gateway.infrastructure.litellm_router_deployment_cooldown_adapter.get_router_sync",
        lambda: router,
    )
    monkeypatch.setattr(
        "domains.gateway.infrastructure.litellm_router_deployment_cooldown_adapter.settings",
        _make_settings(default_seconds=0),
    )

    await adapter.cooldown_deployment(
        deployment_id=str(uuid.uuid4()),
        reason="test",
    )

    router.cooldown_cache.add_deployment_to_cooldown.assert_not_called()


@pytest.mark.asyncio
async def test_cooldown_failure_is_swallowed(
    monkeypatch,
    adapter: LiteLLMRouterDeploymentCooldownAdapter,
) -> None:
    deployment_id = str(uuid.uuid4())
    cooldown_cache = MagicMock()
    cooldown_cache.add_deployment_to_cooldown.side_effect = RuntimeError("boom")
    router = MagicMock()
    router.cooldown_cache = cooldown_cache

    monkeypatch.setattr(
        "domains.gateway.infrastructure.litellm_router_deployment_cooldown_adapter.get_router_sync",
        lambda: router,
    )
    monkeypatch.setattr(
        "domains.gateway.infrastructure.litellm_router_deployment_cooldown_adapter.settings",
        _make_settings(),
    )

    await adapter.cooldown_deployment(
        deployment_id=deployment_id,
        reason="test",
    )
    # 不应抛异常
