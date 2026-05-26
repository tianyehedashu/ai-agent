"""上游厂商方案（Profile）与协议端点领域类型（纯函数 SSOT，无 I/O）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
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
    """Volcengine：Coding Plan 根 ``/api/coding`` 补 ``/v3``；标准根 ``/api`` 补 ``/v3``。"""
    if base.endswith("/v3"):
        return base
    if base.endswith("/api/coding"):
        return f"{base}/v3"
    if base.endswith("/api"):
        return f"{base}/v3"
    return f"{base}/v3"


_VOLCENGINE_OPENAI_NORMALIZE = NormalizeRule(
    apply=_ensure_volcengine_openai_compat_base,
    description="volcengine openai-compat: ensure /v3 suffix",
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
    probe_supported: bool = True
    probe_unsupported_reason: str | None = None

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
        anthropic_default = self.api_bases.get(UpstreamProtocol.ANTHROPIC_NATIVE)
        openai_default = self.api_bases.get(UpstreamProtocol.OPENAI_COMPAT)
        if anthropic_default is not None and openai_default is not None:
            # 双根 profile：``api_base`` 列仅存 OpenAI-compat 根
            return anthropic_default.rstrip("/")
        return normalized


def default_profile_id(provider: str) -> str:
    p = (provider or "").strip().lower()
    return f"{p}.default" if p else "custom.default"


__all__ = [
    "_DEEPSEEK_V1_NORMALIZE",
    "_VOLCENGINE_OPENAI_NORMALIZE",
    "NormalizeRule",
    "UpstreamCallShape",
    "UpstreamProfile",
    "UpstreamProtocol",
    "default_profile_id",
]
