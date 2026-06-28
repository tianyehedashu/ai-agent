"""Prompt Cache 中间件：入站注入 cache_control / anthropic-beta，出站解析 cache_hit。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from domains.gateway.domain.provider.provider_inference import infer_provider_name
from domains.gateway.domain.proxy.http_header_merge import merge_anthropic_beta_values
from utils.logging import get_logger

logger = get_logger(__name__)

_PROVIDER_CACHE_CONFIG: dict[str, dict[str, Any]] = {
    "anthropic": {
        "enabled": True,
        "api_param": "cache_control",
        "min_chars": 4096,
        "max_cache_points": 4,
    },
    "deepseek": {
        "enabled": True,
        "api_param": "cache_control",
        "min_chars": 256,
        "max_cache_points": 1,
    },
    "openai": {
        "enabled": True,
        "api_param": None,
        "min_chars": 4096,
        "max_cache_points": 0,
    },
    "dashscope": {"enabled": False},
    "volcengine": {"enabled": False},
    "zhipuai": {"enabled": False},
    "moonshot": {"enabled": False},
}


def _prompt_cache_enabled(tags: dict[str, Any] | None, metadata: dict[str, Any]) -> bool:
    if metadata.get("gateway_prompt_cache") is False:
        return False
    if tags and tags.get("prompt_cache") is False:
        return False
    if tags and tags.get("prompt_cache") is True:
        return True
    return True


def apply_gateway_cache_hit_to_metadata(
    metadata: dict[str, Any],
    usage: dict[str, Any] | None,
) -> None:
    """将 Prompt Cache 命中写入 Gateway metadata（供 request log / callback）。"""
    if parse_cache_hit_from_usage(usage):
        metadata["gateway_cache_hit"] = True


def parse_cache_hit_from_usage(usage: dict[str, Any] | None) -> bool:
    if not usage or not isinstance(usage, dict):
        return False
    details = usage.get("prompt_tokens_details")
    if isinstance(details, dict):
        cached = details.get("cached_tokens", 0)
        if isinstance(cached, int) and cached > 0:
            return True
    cache_read = usage.get("cache_read_input_tokens", 0)
    return isinstance(cache_read, int) and cache_read > 0


@dataclass
class PromptCacheMiddleware:
    """Gateway 出站 Prompt Cache 策略。"""

    def inbound(
        self,
        kwargs: dict[str, Any],
        *,
        model: str,
        tags: dict[str, Any] | None,
    ) -> dict[str, Any]:
        meta = kwargs.get("metadata")
        metadata: dict[str, Any] = meta if isinstance(meta, dict) else {}
        if not _prompt_cache_enabled(tags, metadata):
            return kwargs

        provider = infer_provider_name(model)
        config = _PROVIDER_CACHE_CONFIG.get(provider, {})
        if not config.get("enabled"):
            return kwargs

        # Anthropic 只需要加 header，也是轻量修改；但为保持接口简单仍走拷贝。
        adapted = dict(kwargs)

        if provider == "anthropic":
            headers = dict(adapted.get("extra_headers") or {})
            existing_beta = headers.get("anthropic-beta")
            headers["anthropic-beta"] = merge_anthropic_beta_values(
                str(existing_beta) if existing_beta is not None else None,
                "prompt-caching-2024-07-31",
            )
            adapted["extra_headers"] = headers

        api_param = config.get("api_param")
        if not api_param:
            return adapted

        messages = adapted.get("messages")
        if not isinstance(messages, list):
            return adapted

        min_chars = int(config.get("min_chars", 4096))
        max_points = int(config.get("max_cache_points", 1))
        cache_points = 0
        new_messages: list[dict[str, Any]] = []
        any_changed = False
        for msg in messages:
            if not isinstance(msg, dict):
                new_messages.append(msg)
                continue
            if (
                msg.get("role") == "system"
                and cache_points < max_points
            ):
                content = msg.get("content", "")
                if isinstance(content, str) and len(content) >= min_chars:
                    new_messages.append({**msg, "cache_control": {"type": "ephemeral"}})
                    cache_points += 1
                    any_changed = True
                    continue
            new_messages.append(msg)
        if any_changed:
            adapted["messages"] = new_messages
        return adapted

    def outbound_usage_stats(
        self,
        usage: dict[str, Any] | None,
        *,
        model: str,
    ) -> dict[str, Any]:
        provider = infer_provider_name(model)
        hit = parse_cache_hit_from_usage(usage)
        if hit:
            logger.debug("Prompt cache hit for model=%s provider=%s", model, provider)
        return {"cache_hit": hit}


_prompt_cache_middleware: PromptCacheMiddleware | None = None


def get_prompt_cache_middleware() -> PromptCacheMiddleware:
    global _prompt_cache_middleware  # pylint: disable=global-statement
    if _prompt_cache_middleware is None:
        _prompt_cache_middleware = PromptCacheMiddleware()
    return _prompt_cache_middleware


__all__ = [
    "PromptCacheMiddleware",
    "apply_gateway_cache_hit_to_metadata",
    "get_prompt_cache_middleware",
    "parse_cache_hit_from_usage",
]
