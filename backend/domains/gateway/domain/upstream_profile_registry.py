"""Upstream Profile 注册表（SSOT）。"""

from __future__ import annotations

from domains.gateway.domain.upstream_profile import (
    _DEEPSEEK_V1_NORMALIZE,
    _VOLCENGINE_OPENAI_NORMALIZE,
    ProbeStrategy,
    UpstreamCallShape,
    UpstreamProfile,
    UpstreamProtocol,
    default_profile_id,
)

_VOLCENGINE_STANDARD_OPENAI = "https://ark.cn-beijing.volces.com/api/v3"
_VOLCENGINE_CODING_OPENAI = "https://ark.cn-beijing.volces.com/api/coding/v3"
_VOLCENGINE_CODING_ANTHROPIC = "https://ark.cn-beijing.volces.com/api/coding"

_PROFILES: tuple[UpstreamProfile, ...] = (
    UpstreamProfile(
        id="openai.default",
        provider="openai",
        label="OpenAI 官方",
        api_bases={UpstreamProtocol.OPENAI_COMPAT: "https://api.openai.com/v1"},
    ),
    UpstreamProfile(
        id="anthropic.default",
        provider="anthropic",
        label="Anthropic 官方",
        api_bases={UpstreamProtocol.ANTHROPIC_NATIVE: "https://api.anthropic.com"},
        probe_strategy=ProbeStrategy.NONE,
        probe_protocol=UpstreamProtocol.ANTHROPIC_NATIVE,
        probe_supported=False,
        probe_unsupported_reason=(
            "Anthropic 不提供 OpenAI 兼容的 /v1/models 列举；请手填模型 ID，"
            "或使用带 OpenAI 兼容列表端点的代理。"
        ),
    ),
    UpstreamProfile(
        id="deepseek.default",
        provider="deepseek",
        label="DeepSeek 官方",
        api_bases={UpstreamProtocol.OPENAI_COMPAT: "https://api.deepseek.com/v1"},
        normalize_rules=(_DEEPSEEK_V1_NORMALIZE,),
    ),
    UpstreamProfile(
        id="dashscope.default",
        provider="dashscope",
        label="DashScope 北京（兼容模式）",
        api_bases={
            UpstreamProtocol.OPENAI_COMPAT: "https://dashscope.aliyuncs.com/compatible-mode/v1"
        },
    ),
    UpstreamProfile(
        id="dashscope.intl",
        provider="dashscope",
        label="DashScope 新加坡（兼容模式）",
        api_bases={
            UpstreamProtocol.OPENAI_COMPAT: "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
        },
    ),
    UpstreamProfile(
        id="dashscope.us",
        provider="dashscope",
        label="DashScope 美国弗吉尼亚（兼容模式）",
        api_bases={
            UpstreamProtocol.OPENAI_COMPAT: "https://dashscope-us.aliyuncs.com/compatible-mode/v1"
        },
    ),
    UpstreamProfile(
        id="zhipuai.standard",
        provider="zhipuai",
        label="智谱标准 API",
        api_bases={UpstreamProtocol.OPENAI_COMPAT: "https://open.bigmodel.cn/api/paas/v4"},
    ),
    UpstreamProfile(
        id="zhipuai.coding_plan",
        provider="zhipuai",
        label="智谱 Coding Plan",
        api_bases={UpstreamProtocol.OPENAI_COMPAT: "https://open.bigmodel.cn/api/coding/paas/v4"},
        coding_agent_ua="cursor/1.0",
    ),
    UpstreamProfile(
        id="zhipuai.default",
        provider="zhipuai",
        label="智谱（默认）",
        api_bases={UpstreamProtocol.OPENAI_COMPAT: "https://open.bigmodel.cn/api/paas/v4"},
    ),
    UpstreamProfile(
        id="volcengine.standard",
        provider="volcengine",
        label="火山引擎方舟（标准）",
        api_bases={UpstreamProtocol.OPENAI_COMPAT: _VOLCENGINE_STANDARD_OPENAI},
        normalize_rules=(_VOLCENGINE_OPENAI_NORMALIZE,),
    ),
    UpstreamProfile(
        id="volcengine.coding_plan",
        provider="volcengine",
        label="火山引擎 Coding Plan",
        api_bases={
            UpstreamProtocol.OPENAI_COMPAT: _VOLCENGINE_CODING_OPENAI,
            UpstreamProtocol.ANTHROPIC_NATIVE: _VOLCENGINE_CODING_ANTHROPIC,
        },
        normalize_rules=(_VOLCENGINE_OPENAI_NORMALIZE,),
        default_call_shape=UpstreamCallShape.OPENAI_COMPAT,
        coding_agent_ua="cursor/1.0",
    ),
    UpstreamProfile(
        id="volcengine.default",
        provider="volcengine",
        label="火山引擎方舟（默认）",
        api_bases={UpstreamProtocol.OPENAI_COMPAT: _VOLCENGINE_STANDARD_OPENAI},
        normalize_rules=(_VOLCENGINE_OPENAI_NORMALIZE,),
    ),
    UpstreamProfile(
        id="moonshot.default",
        provider="moonshot",
        label="Kimi 国际站",
        api_bases={UpstreamProtocol.OPENAI_COMPAT: "https://api.moonshot.ai/v1"},
    ),
    UpstreamProfile(
        id="moonshot.cn",
        provider="moonshot",
        label="Kimi 国内站",
        api_bases={UpstreamProtocol.OPENAI_COMPAT: "https://api.moonshot.cn/v1"},
    ),
    UpstreamProfile(
        id="moonshot.coding_plan",
        provider="moonshot",
        label="Kimi Code",
        api_bases={UpstreamProtocol.OPENAI_COMPAT: "https://api.kimi.com/coding/v1"},
        coding_agent_ua="claude-code/1.0",
        fixed_outbound_temperature=1.0,
    ),
    UpstreamProfile(
        id="custom.default",
        provider="custom",
        label="自定义代理",
        api_bases={},
    ),
)

_BY_ID: dict[str, UpstreamProfile] = {p.id: p for p in _PROFILES}


def get_upstream_profile(profile_id: str | None, *, provider: str) -> UpstreamProfile:
    """解析 profile；未知 id 回退到 ``<provider>.default``。"""
    p = provider.lower().strip()
    if profile_id and (pid := profile_id.strip()):
        found = _BY_ID.get(pid)
        if found is not None and found.provider == p:
            return found
    fallback_id = default_profile_id(p)
    return _BY_ID.get(fallback_id) or _BY_ID["custom.default"]


def list_profiles_for_provider(provider: str) -> list[UpstreamProfile]:
    """返回某 provider 下可选 profile（含 default）。"""
    p = provider.lower().strip()
    seen: set[str] = set()
    out: list[UpstreamProfile] = []
    for prof in _PROFILES:
        if prof.provider != p:
            continue
        if prof.id in seen:
            continue
        seen.add(prof.id)
        out.append(prof)
    if default_profile_id(p) not in seen:
        out.append(get_upstream_profile(None, provider=p))
    return sorted(out, key=lambda x: (x.id.endswith(".default"), x.label))


def list_all_upstream_profiles() -> list[UpstreamProfile]:
    """API 列举：唯一 profile 列表。"""
    return list(_BY_ID.values())


def profile_ids_for_provider(provider: str) -> list[str]:
    return [prof.id for prof in list_profiles_for_provider(provider)]


__all__ = [
    "get_upstream_profile",
    "list_all_upstream_profiles",
    "list_profiles_for_provider",
    "profile_ids_for_provider",
]
