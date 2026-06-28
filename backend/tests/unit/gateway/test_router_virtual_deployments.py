"""GatewayRoute.virtual_model → Router model_list 多 deployment 注入。"""

from __future__ import annotations

from unittest.mock import MagicMock
import uuid

from domains.gateway.application.route.route_owner_slug_maps import RouteOwnerSlugContext
from domains.gateway.domain.route.router_model_name import encode_router_model_name
from domains.gateway.infrastructure.litellm.router_singleton import (
    _models_to_deployments,
    _resolve_strategy,
    _routes_to_fallbacks,
    _routes_to_virtual_deployments,
)


def _stub_build_litellm_params(**kwargs):
    return {"model": kwargs["real_model"], "custom_llm_provider": kwargs["provider"]}


def _mk_model(
    *,
    name: str,
    real_model: str,
    provider: str,
    cred_id: uuid.UUID,
    tenant_id: uuid.UUID | None = None,
    capability: str = "chat",
    weight: int = 1,
) -> MagicMock:
    m = MagicMock()
    m.id = uuid.uuid4()
    m.tenant_id = tenant_id
    m.name = name
    m.capability = capability
    m.weight = weight
    m.credential_id = cred_id
    m.provider = provider
    m.real_model = real_model
    m.rpm_limit = None
    m.tpm_limit = None
    m.tags = None
    m.enabled = True
    return m


def _mk_cred(
    *, id_: uuid.UUID, name: str = "cred", tenant_id: uuid.UUID | None = None
) -> MagicMock:
    cred = MagicMock()
    cred.id = id_
    cred.name = name
    cred.tenant_id = tenant_id
    cred.scope = None
    cred.api_key_encrypted = "encrypted-fake"
    cred.api_base = None
    cred.extra = None
    return cred


def _mk_route(
    *,
    virtual_model: str,
    primary_models: list[str],
    tenant_id: uuid.UUID | None = None,
    retry_policy: dict[str, int] | None = None,
    fallbacks_general: list[str] | None = None,
) -> MagicMock:
    r = MagicMock()
    r.id = uuid.uuid4()
    r.tenant_id = tenant_id
    r.virtual_model = virtual_model
    r.primary_models = primary_models
    r.fallbacks_general = fallbacks_general or []
    r.fallbacks_content_policy = []
    r.fallbacks_context_window = []
    r.strategy = "simple-shuffle"
    r.retry_policy = retry_policy
    return r


def test_virtual_route_creates_one_deployment_per_primary(monkeypatch) -> None:
    monkeypatch.setattr(
        "domains.gateway.infrastructure.litellm.router_singleton._build_litellm_params",
        _stub_build_litellm_params,
    )
    team = uuid.uuid4()
    cred_a, cred_b = uuid.uuid4(), uuid.uuid4()
    m_a = _mk_model(
        name="gpt-4o-a", real_model="gpt-4o", provider="openai", cred_id=cred_a, tenant_id=team
    )
    m_b = _mk_model(
        name="gpt-4o-b", real_model="gpt-4o", provider="openai", cred_id=cred_b, tenant_id=team
    )
    creds = {cred_a: _mk_cred(id_=cred_a, name="ka"), cred_b: _mk_cred(id_=cred_b, name="kb")}
    route = _mk_route(
        virtual_model="smart-4o", primary_models=["gpt-4o-a", "gpt-4o-b"], tenant_id=team
    )

    base = _models_to_deployments([m_a, m_b], creds)
    reserved = frozenset(m.name for m in (m_a, m_b))
    virtuals = _routes_to_virtual_deployments(
        [route],
        [m_a, m_b],
        creds,
        reserved_model_names=reserved,
    )
    route_key = encode_router_model_name(team, "smart-4o")
    assert {d["model_name"] for d in base} == {
        encode_router_model_name(team, "gpt-4o-a"),
        encode_router_model_name(team, "gpt-4o-b"),
    }
    assert [d["model_name"] for d in virtuals] == [route_key, route_key]
    cred_ids = {d["model_info"]["gateway_credential_id"] for d in virtuals}
    assert cred_ids == {str(cred_a), str(cred_b)}


def test_virtual_route_deployments_include_litellm_weight(monkeypatch) -> None:
    monkeypatch.setattr(
        "domains.gateway.infrastructure.litellm.router_singleton._build_litellm_params",
        _stub_build_litellm_params,
    )
    team = uuid.uuid4()
    cred_a, cred_b = uuid.uuid4(), uuid.uuid4()
    m_a = _mk_model(
        name="fast",
        real_model="gpt-4o",
        provider="openai",
        cred_id=cred_a,
        tenant_id=team,
        weight=3,
    )
    m_b = _mk_model(
        name="slow",
        real_model="gpt-4o",
        provider="openai",
        cred_id=cred_b,
        tenant_id=team,
        weight=1,
    )
    route = _mk_route(virtual_model="weighted", primary_models=["fast", "slow"], tenant_id=team)
    virtuals = _routes_to_virtual_deployments(
        [route],
        [m_a, m_b],
        {cred_a: _mk_cred(id_=cred_a), cred_b: _mk_cred(id_=cred_b)},
        reserved_model_names=frozenset({"fast", "slow"}),
    )
    assert [d["litellm_params"]["weight"] for d in virtuals] == [3, 1]
    assert [d["model_info"]["weight"] for d in virtuals] == [3, 1]


def test_invalid_deployment_weight_defaults_to_one(monkeypatch) -> None:
    monkeypatch.setattr(
        "domains.gateway.infrastructure.litellm.router_singleton._build_litellm_params",
        _stub_build_litellm_params,
    )
    cred = uuid.uuid4()
    model = _mk_model(
        name="zero",
        real_model="gpt-4o",
        provider="openai",
        cred_id=cred,
        weight=0,
    )
    out = _models_to_deployments([model], {cred: _mk_cred(id_=cred)})
    assert out[0]["litellm_params"]["weight"] == 1
    assert out[0]["model_info"]["weight"] == 1


def test_weighted_pick_strategy_maps_to_litellm_simple_shuffle() -> None:
    weighted = _mk_route(virtual_model="weighted", primary_models=["a"])
    weighted.strategy = "weighted-pick"
    simple = _mk_route(virtual_model="simple", primary_models=["b"])
    simple.strategy = "simple-shuffle"

    assert _resolve_strategy([weighted]) == "simple-shuffle"
    assert _resolve_strategy([weighted, simple]) == "simple-shuffle"


def test_virtual_route_skipped_when_shadowed_by_model_name(monkeypatch) -> None:
    monkeypatch.setattr(
        "domains.gateway.infrastructure.litellm.router_singleton._build_litellm_params",
        _stub_build_litellm_params,
    )
    team = uuid.uuid4()
    cred = uuid.uuid4()
    primary = _mk_model(
        name="gpt-4o", real_model="gpt-4o", provider="openai", cred_id=cred, tenant_id=team
    )
    creds = {cred: _mk_cred(id_=cred)}
    route = _mk_route(virtual_model="gpt-4o", primary_models=["gpt-4o"], tenant_id=team)
    virtuals = _routes_to_virtual_deployments(
        [route],
        [primary],
        creds,
        reserved_model_names=frozenset({"gpt-4o"}),
    )
    assert virtuals == []


def test_virtual_route_cross_provider_deployments(monkeypatch) -> None:
    monkeypatch.setattr(
        "domains.gateway.infrastructure.litellm.router_singleton._build_litellm_params",
        _stub_build_litellm_params,
    )
    team = uuid.uuid4()
    cred_dpsk, cred_vol = uuid.uuid4(), uuid.uuid4()
    m_dpsk = _mk_model(
        name="deepseek-dpsk",
        real_model="deepseek-chat",
        provider="deepseek",
        cred_id=cred_dpsk,
        tenant_id=team,
    )
    m_vol = _mk_model(
        name="deepseek-volc",
        real_model="ep-deepseek-v3",
        provider="volcengine",
        cred_id=cred_vol,
        tenant_id=team,
    )
    creds = {
        cred_dpsk: _mk_cred(id_=cred_dpsk, name="dpsk"),
        cred_vol: _mk_cred(id_=cred_vol, name="volc"),
    }
    route = _mk_route(
        virtual_model="deepseek-any",
        primary_models=["deepseek-dpsk", "deepseek-volc"],
        tenant_id=team,
    )
    virtuals = _routes_to_virtual_deployments(
        [route],
        [m_dpsk, m_vol],
        creds,
        reserved_model_names=frozenset({"deepseek-dpsk", "deepseek-volc"}),
    )
    assert len(virtuals) == 2
    litellm_models = {d["litellm_params"]["model"] for d in virtuals}
    assert litellm_models == {"deepseek-chat", "ep-deepseek-v3"}


def test_virtual_route_skips_missing_primary(monkeypatch) -> None:
    monkeypatch.setattr(
        "domains.gateway.infrastructure.litellm.router_singleton._build_litellm_params",
        _stub_build_litellm_params,
    )
    team = uuid.uuid4()
    cred = uuid.uuid4()
    primary = _mk_model(
        name="real", real_model="gpt-4o", provider="openai", cred_id=cred, tenant_id=team
    )
    creds = {cred: _mk_cred(id_=cred)}
    route = _mk_route(virtual_model="v", primary_models=["real", "ghost"], tenant_id=team)
    virtuals = _routes_to_virtual_deployments(
        [route], [primary], creds, reserved_model_names=frozenset({"real"})
    )
    assert len(virtuals) == 1
    assert virtuals[0]["model_name"] == encode_router_model_name(team, "v")


def test_system_and_team_same_client_name_both_deployed(monkeypatch) -> None:
    """系统级与团队级同名 ``GatewayModel`` 在 Router 中各占一条编码 deployment。"""
    monkeypatch.setattr(
        "domains.gateway.infrastructure.litellm.router_singleton._build_litellm_params",
        _stub_build_litellm_params,
    )
    team = uuid.uuid4()
    cred_sys, cred_team = uuid.uuid4(), uuid.uuid4()
    m_sys = _mk_model(
        name="gpt-4o", real_model="gpt-4o", provider="openai", cred_id=cred_sys, tenant_id=None
    )
    m_team = _mk_model(
        name="gpt-4o", real_model="gpt-4o", provider="openai", cred_id=cred_team, tenant_id=team
    )
    creds = {
        cred_sys: _mk_cred(id_=cred_sys, name="sys", tenant_id=None),
        cred_team: _mk_cred(id_=cred_team, name="team", tenant_id=uuid.uuid4()),
    }
    base = _models_to_deployments([m_sys, m_team], creds)
    assert len(base) == 2
    names = {d["model_name"] for d in base}
    assert names == {
        encode_router_model_name(None, "gpt-4o"),
        encode_router_model_name(team, "gpt-4o"),
    }


def test_virtual_route_falls_back_to_global_gateway_model(monkeypatch) -> None:
    monkeypatch.setattr(
        "domains.gateway.infrastructure.litellm.router_singleton._build_litellm_params",
        _stub_build_litellm_params,
    )
    team = uuid.uuid4()
    cred = uuid.uuid4()
    global_model = _mk_model(
        name="global-gpt", real_model="gpt-4o", provider="openai", cred_id=cred, tenant_id=None
    )
    creds = {cred: _mk_cred(id_=cred)}
    route = _mk_route(virtual_model="team-virtual", primary_models=["global-gpt"], tenant_id=team)
    virtuals = _routes_to_virtual_deployments(
        [route], [global_model], creds, reserved_model_names=frozenset({"global-gpt"})
    )
    assert len(virtuals) == 1
    assert virtuals[0]["model_name"] == encode_router_model_name(team, "team-virtual")


def test_virtual_route_resolves_cross_team_slug_prefixed_primary(monkeypatch) -> None:
    """personal 路由 primary 为 {slug}/{name} 时应解析到 grant team 的 GatewayModel。"""
    monkeypatch.setattr(
        "domains.gateway.infrastructure.litellm.router_singleton._build_litellm_params",
        _stub_build_litellm_params,
    )
    personal_team = uuid.uuid4()
    shared_team = uuid.uuid4()
    shared_slug = "collab-team"
    cred = uuid.uuid4()
    shared_model = _mk_model(
        name="gpt-4o-shared",
        real_model="gpt-4o",
        provider="openai",
        cred_id=cred,
        tenant_id=shared_team,
    )
    creds = {cred: _mk_cred(id_=cred, name="shared-cred")}
    route = _mk_route(
        virtual_model="my-virtual",
        primary_models=[f"{shared_slug}/gpt-4o-shared"],
        tenant_id=personal_team,
    )
    route_slug_contexts = {
        personal_team: RouteOwnerSlugContext(
            slug_to_tenant={shared_slug: shared_team},
            enable_slug_prefix=True,
        ),
    }
    virtuals = _routes_to_virtual_deployments(
        [route],
        [shared_model],
        creds,
        reserved_model_names=frozenset(),
        route_slug_contexts=route_slug_contexts,
    )
    route_key = encode_router_model_name(personal_team, "my-virtual")
    assert len(virtuals) == 1
    assert virtuals[0]["model_name"] == route_key
    assert virtuals[0]["model_info"]["gateway_credential_id"] == str(cred)


def test_virtual_route_deployment_inherits_retry_policy_num_retries(monkeypatch) -> None:
    monkeypatch.setattr(
        "domains.gateway.infrastructure.litellm.router_singleton._build_litellm_params",
        _stub_build_litellm_params,
    )
    team = uuid.uuid4()
    cred_id = uuid.uuid4()
    model = _mk_model(
        name="gpt-4o-a",
        real_model="gpt-4o",
        provider="openai",
        cred_id=cred_id,
        tenant_id=team,
    )
    creds = {cred_id: _mk_cred(id_=cred_id)}
    route = _mk_route(
        virtual_model="smart-4o",
        primary_models=["gpt-4o-a"],
        tenant_id=team,
        retry_policy={"retries": 4},
    )
    virtuals = _routes_to_virtual_deployments(
        [route],
        [model],
        creds,
        reserved_model_names=frozenset(),
    )
    assert virtuals[0]["litellm_params"]["num_retries"] == 4


def test_routes_to_fallbacks_skips_unresolved_target(monkeypatch) -> None:
    monkeypatch.setattr(
        "domains.gateway.infrastructure.litellm.router_singleton._build_litellm_params",
        _stub_build_litellm_params,
    )
    team = uuid.uuid4()
    cred_id = uuid.uuid4()
    backup = _mk_model(
        name="backup-model",
        real_model="gpt-4o-mini",
        provider="openai",
        cred_id=cred_id,
        tenant_id=team,
    )
    route = _mk_route(
        virtual_model="smart-route",
        primary_models=["backup-model"],
        tenant_id=team,
        fallbacks_general=["missing-model", "backup-model"],
    )
    general, cp, cw = _routes_to_fallbacks([route], [backup])
    route_key = encode_router_model_name(team, "smart-route")
    backup_key = encode_router_model_name(team, "backup-model")
    assert general == [{route_key: [backup_key]}]
    assert cp == []
    assert cw == []
