"""deployment-level 单价注入：让 cost-based-routing 在 deployment 间比价。"""

from __future__ import annotations

from unittest.mock import MagicMock
import uuid

from domains.gateway.domain.route.router_model_name import encode_router_model_name
from domains.gateway.infrastructure.litellm.router_singleton import (
    _build_deployment,
    _build_litellm_params,
    _models_to_deployments,
    filter_litellm_params_for_direct_anthropic,
)


def _stub_build_litellm_params(**kwargs):
    """绕过解密；保留 pricing 注入逻辑。"""
    params = {"model": kwargs["real_model"], "custom_llm_provider": kwargs["provider"]}
    pricing = kwargs.get("pricing")
    if pricing:
        for k, v in pricing.items():
            params[k] = v
    if kwargs.get("rpm_limit"):
        params["rpm"] = kwargs["rpm_limit"]
    if kwargs.get("tpm_limit"):
        params["tpm"] = kwargs["tpm_limit"]
    return params


def _mk_model(*, name, real, prov, cred_id, team=None, cap="chat") -> MagicMock:
    m = MagicMock()
    m.id = uuid.uuid4()
    m.team_id = team
    m.name = name
    m.capability = cap
    m.weight = 1
    m.credential_id = cred_id
    m.provider = prov
    m.real_model = real
    m.rpm_limit = None
    m.tpm_limit = None
    m.tags = None
    m.enabled = True
    return m


def _mk_cred(*, id_, name="cred", tenant_id=None):
    cred = MagicMock()
    cred.id = id_
    cred.name = name
    cred.tenant_id = tenant_id
    cred.scope = None
    cred.api_key_encrypted = "enc"
    cred.api_base = None
    cred.extra = None
    return cred


def test_pricing_injected_into_litellm_params(monkeypatch) -> None:
    monkeypatch.setattr(
        "domains.gateway.infrastructure.litellm.router_singleton._build_litellm_params",
        _stub_build_litellm_params,
    )
    cred_id = uuid.uuid4()
    m = _mk_model(name="m", real="gpt-4o", prov="openai", cred_id=cred_id)
    lookup = {
        ("openai", "gpt-4o", "chat"): {
            "input_cost_per_token": 1.5e-6,
            "output_cost_per_token": 6e-6,
        }
    }
    out = _models_to_deployments([m], {cred_id: _mk_cred(id_=cred_id)}, lookup)
    assert len(out) == 1
    params = out[0]["litellm_params"]
    assert params["input_cost_per_token"] == 1.5e-6
    assert params["output_cost_per_token"] == 6e-6


def test_pricing_lookup_misses_keep_params_minimal(monkeypatch) -> None:
    monkeypatch.setattr(
        "domains.gateway.infrastructure.litellm.router_singleton._build_litellm_params",
        _stub_build_litellm_params,
    )
    cred_id = uuid.uuid4()
    m = _mk_model(name="m", real="foo", prov="openai", cred_id=cred_id)
    out = _models_to_deployments([m], {cred_id: _mk_cred(id_=cred_id)}, pricing_lookup={})
    params = out[0]["litellm_params"]
    assert "input_cost_per_token" not in params
    assert "output_cost_per_token" not in params


def test_pricing_keys_filtered_for_direct_anthropic_call() -> None:
    dep = {
        "model": "anthropic/claude-3-haiku-20240307",
        "api_key": "sk",
        "rpm": 60,
        "tpm": 10000,
        "input_cost_per_token": 2e-7,
        "output_cost_per_token": 1.25e-6,
    }
    filtered = filter_litellm_params_for_direct_anthropic(dep)
    assert "input_cost_per_token" not in filtered
    assert "output_cost_per_token" not in filtered
    assert "rpm" not in filtered
    assert filtered["api_key"] == "sk"


def test_build_deployment_pricing_injected_via_capability_key(monkeypatch) -> None:
    monkeypatch.setattr(
        "domains.gateway.infrastructure.litellm.router_singleton._build_litellm_params",
        _stub_build_litellm_params,
    )
    cred_id = uuid.uuid4()
    image = _mk_model(name="img", real="dall-e-3", prov="openai", cred_id=cred_id, cap="image")
    lookup = {
        ("openai", "dall-e-3", "image"): {"input_cost_per_token": 0.04},
        ("openai", "dall-e-3", "chat"): {"input_cost_per_token": 99},  # 干扰项
    }
    dep = _build_deployment(
        model_name=image.name,
        src=image,
        cred=_mk_cred(id_=cred_id),
        pricing_lookup=lookup,
    )
    assert dep["litellm_params"]["input_cost_per_token"] == 0.04


def test_build_litellm_params_pricing_argument() -> None:
    cred = _mk_cred(id_=uuid.uuid4())
    params = _build_litellm_params(
        real_model="gpt-4o-mini",
        provider="openai",
        credential=cred,
        rpm_limit=None,
        tpm_limit=None,
        tags=None,
        pricing={"input_cost_per_token": 1.5e-7, "output_cost_per_token": 6e-7},
    )
    assert params["input_cost_per_token"] == 1.5e-7
    assert params["output_cost_per_token"] == 6e-7
