"""``proxy_litellm_kwargs`` 纯函数单测。"""

from __future__ import annotations

from unittest.mock import MagicMock

from domains.gateway.application.proxy_litellm_kwargs import optional_body_model


def test_optional_body_model_missing() -> None:
    assert optional_body_model({}) is None


def test_optional_body_model_strips() -> None:
    assert optional_body_model({"model": "  gpt-4o  "}) == "gpt-4o"


def test_optional_body_model_blank_is_none() -> None:
    assert optional_body_model({"model": "   "}) is None


def test_kwargs_from_prepared_applies_upstream_and_cache() -> None:
    from domains.gateway.application.proxy_litellm_kwargs import kwargs_from_prepared
    from domains.gateway.application.proxy_metadata_builder import PreparedLitellmKwargs

    upstream = MagicMock()
    upstream.adapt.return_value = {"model": "router-name", "messages": []}
    cache = MagicMock()
    cache.inbound.return_value = {"model": "router-name", "cached": True}

    prepared = PreparedLitellmKwargs(
        kwargs={"model": "client-model"},
        client_model="client-model",
        resolved=None,
    )
    out = kwargs_from_prepared(
        prepared,
        upstream_adapter=upstream,
        prompt_cache=cache,
    )
    upstream.adapt.assert_called_once()
    cache.inbound.assert_called_once()
    assert out["cached"] is True
