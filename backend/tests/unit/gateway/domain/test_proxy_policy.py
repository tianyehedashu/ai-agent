"""domains.gateway.domain.proxy_policy 纯函数单测。"""

from __future__ import annotations

import pytest

from domains.gateway.domain.proxy_policy import (
    allows_unregistered_gateway_model,
    is_router_model_miss,
)


@pytest.mark.parametrize(
    ("vkey_is_system", "disable_direct", "expected"),
    [
        (True, False, True),
        (True, True, False),
        (False, False, False),
        (None, False, False),
    ],
)
def test_allows_unregistered_gateway_model(
    vkey_is_system: bool | None,
    disable_direct: bool,
    expected: bool,
) -> None:
    assert (
        allows_unregistered_gateway_model(
            vkey_is_system=vkey_is_system,
            disable_internal_direct_litellm=disable_direct,
        )
        is expected
    )


def test_is_router_model_miss_recognizes_healthy_deployments_error() -> None:
    exc = RuntimeError(
        "litellm.BadRequestError: no healthy deployments for model=foo"
    )
    assert is_router_model_miss(exc) is True


def test_is_router_model_miss_ignores_unrelated_errors() -> None:
    assert is_router_model_miss(ValueError("timeout")) is False
