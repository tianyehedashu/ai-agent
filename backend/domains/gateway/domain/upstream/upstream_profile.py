"""上游厂商方案（Profile）与协议端点领域类型（纯函数 SSOT，无 I/O）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping


class UpstreamProtocol(StrEnum):
    """凭据/部署解析 api_base 时使用的协议面。"""

    OPENAI_COMPAT = "openai_compat"
    ANTHROPIC_NATIVE = "anthropic_native"


class UpstreamCallShape(StrEnum):
    """模型出站 LiteLLM 调用形（与入站 HTTP 面可不同）。"""

    OPENAI_COMPAT = "openai_compat"
    ANTHROPIC_NATIVE = "anthropic_native"


class ProbeStrategy(StrEnum):
    """凭据上游模型发现策略。"""

    OPENAI_MODELS_LIST = "openai_models_list"
    NONE = "none"


_VERSION_PATH_SUFFIX = re.compile(r"/v\d+$")


@dataclass(frozen=True)
class NormalizeRule:
    """对用户覆盖的 api_base 做规范化（探测与 Router 共用）。"""

    apply: Callable[[str], str]
    description: str = ""

    def __call__(self, base: str) -> str:
        return self.apply(base.rstrip("/"))


def _append_suffix_if_missing(suffix: str) -> NormalizeRule:
    def _apply(base: str) -> str:
        if base.endswith(suffix):
            return base
        return f"{base}{suffix}"

    return NormalizeRule(apply=_apply, description=f"append {suffix!r} if missing")


def _ensure_volcengine_openai_compat_base(base: str) -> str:
    """Volcengine：已有 ``/vN`` 后缀则保留；否则对 ``/api/coding`` 或 ``/api`` 补 ``/v3``。"""
    if _VERSION_PATH_SUFFIX.search(base):
        return base
    if base.endswith("/api/coding"):
        return f"{base}/v3"
    if base.endswith("/api"):
        return f"{base}/v3"
    return f"{base}/v3"


_VOLCENGINE_OPENAI_NORMALIZE = NormalizeRule(
    apply=_ensure_volcengine_openai_compat_base,
    description="volcengine openai-compat: ensure /v3 suffix when no version segment",
)
_DEEPSEEK_V1_NORMALIZE = _append_suffix_if_missing("/v1")


@dataclass(frozen=True)
class UpstreamProfile:
    """(provider, plan) 的端点与探测策略。"""

    id: str
    provider: str
    label: str
    api_bases: Mapping[UpstreamProtocol, str]
    models_list_path: str = "/models"
    normalize_rules: tuple[NormalizeRule, ...] = field(default_factory=tuple)
    default_call_shape: UpstreamCallShape = UpstreamCallShape.OPENAI_COMPAT
    probe_strategy: ProbeStrategy = ProbeStrategy.OPENAI_MODELS_LIST
    probe_protocol: UpstreamProtocol = UpstreamProtocol.OPENAI_COMPAT
    probe_supported: bool = True
    probe_unsupported_reason: str | None = None
    coding_agent_ua: str | None = None
    fixed_outbound_temperature: float | None = None
    """出站 LiteLLM 须锁定的 temperature；``None`` 表示不强制。"""

    def normalize_api_base(self, api_base: str | None, *, protocol: UpstreamProtocol) -> str | None:
        """用户覆盖或 profile 默认 base，经 normalize_rules 规范化。"""
        raw = (api_base or "").strip()
        if not raw:
            return self.api_bases.get(protocol)
        normalized = raw.rstrip("/")
        if protocol == UpstreamProtocol.OPENAI_COMPAT:
            for rule in self.normalize_rules:
                normalized = rule(normalized)
            return normalized
        return normalized


def default_profile_id(provider: str) -> str:
    p = (provider or "").strip().lower()
    return f"{p}.default" if p else "custom.default"


__all__ = [
    "_DEEPSEEK_V1_NORMALIZE",
    "_VOLCENGINE_OPENAI_NORMALIZE",
    "NormalizeRule",
    "ProbeStrategy",
    "UpstreamCallShape",
    "UpstreamProfile",
    "UpstreamProtocol",
    "default_profile_id",
]
