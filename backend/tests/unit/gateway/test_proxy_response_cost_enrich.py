"""proxy 响应注入 response_cost（OpenAI 兼容扩展字段）。"""

from types import SimpleNamespace

from domains.gateway.application.proxy_use_case import _enrich_openai_compat_response_cost


def test_enrich_uses_hidden_params_response_cost() -> None:
    obj = SimpleNamespace(_hidden_params={"response_cost": 0.42})
    data = {"usage": {"total_tokens": 10}}
    out = _enrich_openai_compat_response_cost(
        data,
        source_obj=obj,
        metadata={},
        downstream_custom=None,
        model="m",
    )
    assert out["response_cost"] == 0.42


def test_enrich_skips_when_already_present() -> None:
    data = {"response_cost": 0.1, "usage": {"total_tokens": 1}}
    out = _enrich_openai_compat_response_cost(
        data,
        source_obj=SimpleNamespace(_hidden_params={"response_cost": 0.9}),
        metadata={},
        downstream_custom=None,
        model="m",
    )
    assert out["response_cost"] == 0.1
