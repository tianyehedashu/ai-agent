"""统一 usage 值对象与提取函数 — 所有 token 提取路径的唯一 SSOT（纯函数，无 I/O）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from domains.gateway.domain.pricing.pricing_calculator import TokenUsage


@dataclass(frozen=True)
class NormalizedUsage:
    """统一 usage 值对象 — 所有提取路径的唯一 SSOT。

    语义约定：
    - ``input_tokens_raw``: 上游原始值（Anthropic = 仅 non-cached 部分；
      OpenAI = ``prompt_tokens - cached_tokens``，使 normalized 后与 prompt_tokens 对齐）
    - ``output_tokens``: completion / output tokens
    - ``cache_read_tokens``: ``cache_read_input_tokens`` / ``prompt_tokens_details.cached_tokens``
    - ``cache_creation_tokens``: ``cache_creation_input_tokens``
    - ``requests``: 请求数（默认 1）
    """

    input_tokens_raw: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    requests: int = 1

    # ---- 派生视图 ----

    @property
    def input_tokens_normalized(self) -> int:
        """与 OpenAI ``prompt_tokens`` 对齐（含所有 cache tokens）。"""
        return self.input_tokens_raw + self.cache_read_tokens + self.cache_creation_tokens

    @property
    def total_tokens(self) -> int:
        """所有 token 总和（预算 / 限流用）。"""
        return self.input_tokens_normalized + self.output_tokens

    @property
    def cached_tokens_for_db(self) -> int:
        """DB ``cached_tokens`` 列值：仅 ``cache_read``（与 OpenAI cached_tokens 一致）。"""
        return self.cache_read_tokens

    # ---- 转换 ----

    def to_token_usage(self) -> TokenUsage:
        """转为 pricing 层 ``TokenUsage``（4 字段独立，用于 ``calculate_cost_from_rate``）。"""
        from domains.gateway.domain.pricing.pricing_calculator import TokenUsage

        return TokenUsage(
            input_tokens=self.input_tokens_normalized,
            output_tokens=self.output_tokens,
            cache_creation_tokens=self.cache_creation_tokens,
            cache_read_tokens=self.cache_read_tokens,
            requests=self.requests,
        )

    def to_db_tuple(self) -> tuple[int, int, int]:
        """DB 写入三元组: ``(input_normalized, output, cache_read)``。"""
        return (self.input_tokens_normalized, self.output_tokens, self.cached_tokens_for_db)

    # ---- SLO 补充 ----

    def with_slo_fallback(self, slo: dict[str, Any] | None) -> NormalizedUsage:
        """当 SLO 提供更完整 cache 信息时，返回增强副本（仅原始值缺失时补齐）。"""
        if not isinstance(slo, dict):
            return self
        slo_cached = int(slo.get("cache_read_input_tokens") or 0)
        slo_creation = int(slo.get("cache_creation_input_tokens") or 0)
        if slo_cached == 0 and slo_creation == 0:
            return self
        # 仅当原始提取的 cache 字段全为 0 时才用 SLO 补齐
        if self.cache_read_tokens > 0 or self.cache_creation_tokens > 0:
            return self
        # SLO 有 cache 数据，原始提取没有 → 补齐
        new_raw = self.input_tokens_raw
        if new_raw == 0:
            # input_tokens 也未提取到 → 全部归入 cache 字段
            return NormalizedUsage(
                input_tokens_raw=0,
                output_tokens=self.output_tokens,
                cache_read_tokens=slo_cached,
                cache_creation_tokens=slo_creation,
                requests=self.requests,
            )
        # input_tokens_raw 已有值 → 只补 cache 字段
        return NormalizedUsage(
            input_tokens_raw=new_raw,
            output_tokens=self.output_tokens,
            cache_read_tokens=slo_cached,
            cache_creation_tokens=slo_creation,
            requests=self.requests,
        )


# ---- 提取函数 ----


def _usage_get(usage: Any, key: str, default: Any = None) -> Any:
    """从 dict 或 object usage 中安全读取字段。"""
    if isinstance(usage, dict):
        return usage.get(key, default)
    return getattr(usage, key, default)


def extract_normalized_usage(response_obj: Any, *, requests: int = 1) -> NormalizedUsage:
    """从 ``response_obj.usage`` 提取统一的 ``NormalizedUsage``。

    支持格式：

    1. OpenAI: ``prompt_tokens`` / ``completion_tokens`` / ``prompt_tokens_details.cached_tokens``
    2. Anthropic: ``input_tokens`` / ``output_tokens`` /
       ``cache_read_input_tokens`` / ``cache_creation_input_tokens``
    3. dict 或 object 两种容器
    """
    if response_obj is None:
        return NormalizedUsage(requests=requests)
    usage = getattr(response_obj, "usage", None)
    if usage is None and isinstance(response_obj, dict):
        usage = response_obj.get("usage")
    if usage is None:
        return NormalizedUsage(requests=requests)
    return _extract_from_usage(usage, requests=requests)


def normalized_usage_from_raw(usage: Any, *, requests: int = 1) -> NormalizedUsage:
    """直接接受 usage dict/object（非 ``response_obj``），适配已有调用方。"""
    if usage is None:
        return NormalizedUsage(requests=requests)
    return _extract_from_usage(usage, requests=requests)


def _extract_from_usage(usage: Any, *, requests: int = 1) -> NormalizedUsage:
    """内部：从 usage dict/object 提取并归一化。"""

    # OpenAI 格式
    prompt_tokens = int(_usage_get(usage, "prompt_tokens", 0) or 0)
    completion_tokens = int(_usage_get(usage, "completion_tokens", 0) or 0)

    # Anthropic 格式
    input_tokens = int(_usage_get(usage, "input_tokens", 0) or 0)
    output_tokens = int(_usage_get(usage, "output_tokens", 0) or 0)
    cache_read = int(_usage_get(usage, "cache_read_input_tokens", 0) or 0)
    cache_creation = int(_usage_get(usage, "cache_creation_input_tokens", 0) or 0)

    # OpenAI cache: prompt_tokens_details.cached_tokens
    openai_cached = 0
    cache_details = _usage_get(usage, "prompt_tokens_details", None)
    if isinstance(cache_details, dict):
        openai_cached = int(cache_details.get("cached_tokens", 0) or 0)
    elif cache_details is not None:
        openai_cached = int(getattr(cache_details, "cached_tokens", 0) or 0)

    if prompt_tokens > 0:
        # OpenAI 路径: prompt_tokens 已含 cached → raw = prompt_tokens - cached
        raw_cached = openai_cached
        raw_input = max(0, prompt_tokens - raw_cached)
        return NormalizedUsage(
            input_tokens_raw=raw_input,
            output_tokens=completion_tokens,
            cache_read_tokens=raw_cached,
            cache_creation_tokens=0,
            requests=requests,
        )

    if input_tokens > 0 or cache_read > 0 or cache_creation > 0:
        # Anthropic 路径: input_tokens 天然 non-cached
        return NormalizedUsage(
            input_tokens_raw=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read,
            cache_creation_tokens=cache_creation,
            requests=requests,
        )

    # Fallback: LiteLLM 流式 usage 仅含 total_tokens
    total = int(_usage_get(usage, "total_tokens", 0) or 0)
    if total > 0:
        return NormalizedUsage(output_tokens=total, requests=requests)

    # completion_tokens 独立存在（无 prompt_tokens）
    if completion_tokens > 0:
        return NormalizedUsage(output_tokens=completion_tokens, requests=requests)

    return NormalizedUsage(requests=requests)


__all__ = [
    "NormalizedUsage",
    "extract_normalized_usage",
    "normalized_usage_from_raw",
]
