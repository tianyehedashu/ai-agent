"""``route_retry_policy`` — 路由 retry_policy → LiteLLM Router 参数。"""

from __future__ import annotations

from types import SimpleNamespace
import uuid

from domains.gateway.domain.route.route_retry_policy import (
    DEFAULT_ROUTER_NUM_RETRIES,
    deployment_num_retries_from_policy,
    litellm_model_group_retry_policy,
    routes_to_model_group_retry_policy,
)
from domains.gateway.domain.route.router_model_name import encode_router_model_name


def test_deployment_num_retries_accepts_shorthand() -> None:
    assert deployment_num_retries_from_policy({"retries": 3}) == 3
    assert deployment_num_retries_from_policy({"num_retries": "1"}) == 1
    assert deployment_num_retries_from_policy(None) is None
    assert deployment_num_retries_from_policy({"RateLimitErrorRetries": 2}) is None


def test_litellm_model_group_retry_policy_filters_shorthand() -> None:
    policy = {
        "retries": 2,
        "RateLimitErrorRetries": 4,
        "TimeoutErrorRetries": 1,
    }
    assert litellm_model_group_retry_policy(policy) == {
        "RateLimitErrorRetries": 4,
        "TimeoutErrorRetries": 1,
    }


def test_routes_to_model_group_retry_policy_keys_by_encoded_virtual_model() -> None:
    team = uuid.uuid4()
    route = SimpleNamespace(
        virtual_model="smart-route",
        tenant_id=team,
        retry_policy={"RateLimitErrorRetries": 5},
    )
    out = routes_to_model_group_retry_policy([route])
    assert out == {encode_router_model_name(team, "smart-route"): {"RateLimitErrorRetries": 5}}


def test_default_router_num_retries_is_two() -> None:
    assert DEFAULT_ROUTER_NUM_RETRIES == 2
