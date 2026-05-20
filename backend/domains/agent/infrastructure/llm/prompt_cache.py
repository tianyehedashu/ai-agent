"""向后兼容：Prompt Cache 已下沉至 Gateway ``prompt_cache_middleware``。"""

from domains.gateway.application.prompt_cache_middleware import (
    PromptCacheMiddleware,
    get_prompt_cache_middleware,
    parse_cache_hit_from_usage,
)

__all__ = [
    "PromptCacheMiddleware",
    "get_prompt_cache_middleware",
    "parse_cache_hit_from_usage",
]
