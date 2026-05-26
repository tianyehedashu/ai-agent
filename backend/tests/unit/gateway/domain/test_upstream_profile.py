"""upstream_profile / upstream_endpoint 纯函数行为。"""

from __future__ import annotations

from domains.gateway.domain.upstream_endpoint import (
    infer_profile_id_from_env_api_base,
    resolve_openai_compat_api_base_for_storage,
    resolve_upstream_endpoint,
)
from domains.gateway.domain.upstream_profile import UpstreamProtocol
from domains.gateway.domain.upstream_profile_registry import get_upstream_profile


def test_volcengine_coding_plan_appends_v3_when_user_omits_suffix() -> None:
    base = resolve_openai_compat_api_base_for_storage(
        provider="volcengine",
        profile_id="volcengine.coding_plan",
        api_base="https://ark.cn-beijing.volces.com/api/coding",
    )
    assert base == "https://ark.cn-beijing.volces.com/api/coding/v3"


def test_volcengine_standard_appends_v3_when_user_omits_suffix() -> None:
    base = resolve_openai_compat_api_base_for_storage(
        provider="volcengine",
        profile_id="volcengine.standard",
        api_base="https://ark.cn-beijing.volces.com/api",
    )
    assert base == "https://ark.cn-beijing.volces.com/api/v3"


def test_deepseek_appends_v1_when_user_omits_suffix() -> None:
    base = resolve_openai_compat_api_base_for_storage(
        provider="deepseek",
        profile_id=None,
        api_base="https://api.deepseek.com",
    )
    assert base == "https://api.deepseek.com/v1"


def test_volcengine_coding_plan_anthropic_native_root() -> None:
    base = resolve_upstream_endpoint(
        provider="volcengine",
        profile_id="volcengine.coding_plan",
        api_base=None,
        protocol=UpstreamProtocol.ANTHROPIC_NATIVE,
    )
    assert base == "https://ark.cn-beijing.volces.com/api/coding"


def test_get_upstream_profile_fallback_to_default() -> None:
    prof = get_upstream_profile(None, provider="volcengine")
    assert prof.id == "volcengine.default"


def test_infer_profile_id_from_env_api_base() -> None:
    assert (
        infer_profile_id_from_env_api_base(
            "volcengine",
            api_base="https://ark.cn-beijing.volces.com/api/coding/v3",
        )
        == "volcengine.coding_plan"
    )
    assert (
        infer_profile_id_from_env_api_base(
            "dashscope",
            api_base="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        )
        == "dashscope.intl"
    )
    assert (
        infer_profile_id_from_env_api_base(
            "zhipuai",
            api_base="https://open.bigmodel.cn/api/coding/paas/v4",
        )
        == "zhipuai.coding_plan"
    )
    assert infer_profile_id_from_env_api_base("openai", api_base=None) is None


def test_list_profiles_for_provider_includes_multi_plan_vendors() -> None:
    from domains.gateway.domain.upstream_profile_registry import list_profiles_for_provider

    volc = {p.id for p in list_profiles_for_provider("volcengine")}
    assert "volcengine.standard" in volc
    assert "volcengine.coding_plan" in volc

    zhipu = {p.id for p in list_profiles_for_provider("zhipuai")}
    assert "zhipuai.standard" in zhipu
    assert "zhipuai.coding_plan" in zhipu

    dash = {p.id for p in list_profiles_for_provider("dashscope")}
    assert "dashscope.default" in dash
    assert "dashscope.intl" in dash
    assert "dashscope.us" in dash
