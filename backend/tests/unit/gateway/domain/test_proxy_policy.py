"""domains.gateway.domain.proxy.proxy_policy 纯函数单测。"""

from __future__ import annotations

import uuid

import pytest

from domains.gateway.domain.proxy.proxy_policy import (
    allows_unregistered_gateway_model,
    build_budget_check_plan,
    is_reportable_upstream_proxy_exception,
    is_router_deployment_cooldown,
    is_router_model_miss,
    is_router_unavailable_wrapper,
    proxy_budget_targets,
    resolve_upstream_proxy_exception,
    router_cooldown_retry_after,
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
    exc = RuntimeError("litellm.BadRequestError: no healthy deployments for model=foo")
    assert is_router_model_miss(exc) is True


def test_is_router_model_miss_ignores_unrelated_errors() -> None:
    assert is_router_model_miss(ValueError("timeout")) is False


def test_is_router_deployment_cooldown_recognizes_router_rate_limit_error() -> None:
    from litellm.types.router import RouterRateLimitError

    exc = RouterRateLimitError(
        model="gw/t/x/m",
        cooldown_time=60,
        enable_pre_call_checks=True,
        cooldown_list=["dep-1"],
    )
    assert is_router_deployment_cooldown(exc) is True
    assert is_router_model_miss(exc) is False
    assert router_cooldown_retry_after(exc) == 60


def test_is_router_deployment_cooldown_from_message() -> None:
    exc = RuntimeError("No deployments available for selected model, Try again in 45 seconds.")
    assert is_router_deployment_cooldown(exc) is True
    assert is_router_model_miss(exc) is False
    assert router_cooldown_retry_after(exc) == 45


def test_is_router_unavailable_wrapper() -> None:
    miss = RuntimeError("no healthy deployments for model=foo")
    assert is_router_unavailable_wrapper(miss) is True
    assert is_router_unavailable_wrapper(ValueError("bad input")) is False


def test_resolve_upstream_proxy_exception_from_router_wrapper() -> None:
    import litellm

    auth = litellm.AuthenticationError(
        message="The API key doesn't exist",
        llm_provider="volcengine",
        model="GLM-5.1",
    )
    wrapper = litellm.BadRequestError(
        message="no healthy deployments for model=gw/t/x/m",
        model="gw/t/x/m",
        llm_provider="",
    )
    wrapper.__cause__ = auth
    resolved = resolve_upstream_proxy_exception(wrapper)
    assert resolved is auth


def test_is_reportable_upstream_proxy_exception() -> None:
    import litellm

    auth = litellm.AuthenticationError(
        message="bad key",
        llm_provider="openai",
        model="gpt-4o",
    )
    assert is_reportable_upstream_proxy_exception(auth) is True
    assert is_reportable_upstream_proxy_exception(ValueError("local")) is False
    wrapper = litellm.BadRequestError(
        message="no healthy deployments",
        model="m",
        llm_provider="",
    )
    assert is_reportable_upstream_proxy_exception(wrapper) is False


def test_proxy_budget_targets_includes_system() -> None:
    tid = uuid.uuid4()
    uid = uuid.uuid4()
    vid = uuid.uuid4()
    targets = proxy_budget_targets(tenant_id=tid, user_id=uid, vkey_id=vid)
    assert targets[0] == ("system", None)
    assert ("tenant", tid) in targets
    assert ("user", uid) in targets
    assert ("key", vid) in targets


def test_build_budget_check_plan_includes_system_without_target_id() -> None:
    tid = uuid.uuid4()
    plan = build_budget_check_plan(
        targets=(("system", None), ("tenant", tid)),
        periods=("daily",),
        request_model=None,
    )
    kinds = {q.target_kind for q in plan}
    assert "system" in kinds
    assert any(q.target_kind == "system" and q.target_id is None for q in plan)


def test_build_budget_check_plan_scopes_tenant_only_to_user_target() -> None:
    """tenant_id 仅施加于 user 维度（成员总量/模型护栏按团队隔离）。"""
    team_id = uuid.uuid4()
    user_id = uuid.uuid4()
    plan = build_budget_check_plan(
        targets=(("system", None), ("tenant", team_id), ("user", user_id)),
        periods=("daily",),
        request_model=None,
        tenant_id=team_id,
    )
    by_kind = {q.target_kind: q for q in plan}
    assert by_kind["user"].tenant_id == team_id
    assert by_kind["tenant"].tenant_id is None
    assert by_kind["system"].tenant_id is None
