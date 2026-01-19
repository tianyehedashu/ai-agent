"""
Prompt Cache Manager - 提示词缓存管理器

实现云厂商的提示词缓存功能，支持：
- Anthropic: cache_control API（90% 折扣）
- DeepSeek: cache_control API（50% 折扣）
- OpenAI: 自动缓存（无需特殊处理，50% 折扣）

2026 年主流的 Agent Token 优化策略中，提示词缓存是最有效的成本控制手段。
"""

from dataclasses import dataclass
from typing import Any, ClassVar, Literal

from core.llm.providers import get_provider_name
from utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class CacheableContent:
    """可缓存的内容"""

    content: str
    cache_type: Literal["ephemeral", "persistent"] = "ephemeral"
    priority: int = 0  # 缓存优先级，越高越优先保留


@dataclass
class CacheStats:
    """缓存统计"""

    hits: int = 0
    misses: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    estimated_savings: float = 0.0

    @property
    def hit_rate(self) -> float:
        """缓存命中率"""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


class PromptCacheManager:
    """
    提示词缓存管理器

    设计原则：
    1. 系统提示词优先缓存（变化频率最低）
    2. 长期记忆次优先（用户偏好等稳定信息）
    3. 短期上下文不缓存（变化频繁）

    支持的云厂商缓存配置：
    - Anthropic: 90% 折扣，最多 4 个缓存断点，最小 1024 tokens
    - DeepSeek: 50% 折扣，最多 1 个缓存断点，最小 64 tokens
    - OpenAI: 50% 折扣，自动缓存无需特殊处理
    """

    # 各厂商的缓存配置
    PROVIDER_CACHE_CONFIG: ClassVar[dict[str, dict[str, Any]]] = {
        "anthropic": {
            "enabled": True,
            "discount": 0.1,  # 缓存命中时只收 10%
            "api_param": "cache_control",
            "min_tokens": 1024,  # 最小缓存 token 数
            "max_cache_points": 4,  # 最多 4 个缓存断点
            "min_chars": 4096,  # 最小字符数估算（1 token ≈ 4 字符）
        },
        "deepseek": {
            "enabled": True,
            "discount": 0.5,
            "api_param": "cache_control",
            "min_tokens": 64,
            "max_cache_points": 1,
            "min_chars": 256,
        },
        "openai": {
            "enabled": True,
            "discount": 0.5,  # OpenAI 缓存折扣 50%
            "api_param": None,  # OpenAI 自动缓存，无需特殊参数
            "min_tokens": 1024,
            "max_cache_points": 0,
            "min_chars": 4096,
        },
        "dashscope": {
            "enabled": False,  # 阿里云暂不支持提示词缓存
            "discount": 1.0,
            "api_param": None,
            "min_tokens": 0,
            "max_cache_points": 0,
            "min_chars": 0,
        },
        "volcengine": {
            "enabled": False,  # 火山引擎暂不支持提示词缓存
            "discount": 1.0,
            "api_param": None,
            "min_tokens": 0,
            "max_cache_points": 0,
            "min_chars": 0,
        },
        "zhipuai": {
            "enabled": False,  # 智谱AI暂不支持提示词缓存
            "discount": 1.0,
            "api_param": None,
            "min_tokens": 0,
            "max_cache_points": 0,
            "min_chars": 0,
        },
    }

    def __init__(self) -> None:
        self._stats = CacheStats()

    def get_provider_from_model(self, model: str) -> str:
        """
        根据模型名称推断提供商

        复用 providers.py 中的统一逻辑，确保一致性。

        Args:
            model: 模型名称

        Returns:
            提供商名称
        """
        return get_provider_name(model)

    def is_cache_supported(self, model: str) -> bool:
        """
        检查模型是否支持缓存

        Args:
            model: 模型名称

        Returns:
            是否支持缓存
        """
        provider = self.get_provider_from_model(model)
        config = self.PROVIDER_CACHE_CONFIG.get(provider, {})
        return config.get("enabled", False)

    def prepare_cacheable_messages(
        self,
        messages: list[dict[str, Any]],
        model: str,
        system_prompt: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        准备可缓存的消息列表

        对于支持缓存的提供商，在适当位置添加 cache_control 标记。

        缓存策略：
        1. 系统提示词（如果存在且足够长）
        2. 前几条消息（上下文建立阶段）

        Args:
            messages: 原始消息列表
            model: 模型名称
            system_prompt: 系统提示词（可选，如果消息列表中没有）

        Returns:
            添加了缓存标记的消息列表
        """
        provider = self.get_provider_from_model(model)
        config = self.PROVIDER_CACHE_CONFIG.get(provider, {})

        if not config.get("enabled"):
            return messages

        api_param = config.get("api_param")
        if not api_param:
            # OpenAI 自动缓存，直接返回
            return messages

        min_chars = config.get("min_chars", 4096)
        max_cache_points = config.get("max_cache_points", 1)

        # 复制消息列表，避免修改原始数据
        cached_messages = []
        cache_points_used = 0

        for msg in messages:
            msg_copy = msg.copy()

            # 只对系统消息添加缓存标记
            if msg_copy.get("role") == "system" and cache_points_used < max_cache_points:
                content = msg_copy.get("content", "")
                # 检查是否满足最小字符要求
                if len(content) >= min_chars:
                    msg_copy["cache_control"] = {"type": "ephemeral"}
                    cache_points_used += 1
                    logger.debug(
                        "Added cache control to system message (cache point %d/%d, content length %d)",
                        cache_points_used,
                        max_cache_points,
                        len(content),
                    )

            cached_messages.append(msg_copy)

        return cached_messages

    def format_for_anthropic(
        self,
        messages: list[dict[str, Any]],
        system_prompt: str | None = None,
    ) -> tuple[str | list[dict[str, Any]] | None, list[dict[str, Any]]]:
        """
        格式化消息为 Anthropic API 格式

        Anthropic 的 system 参数需要单独传递，不在 messages 中。
        如果系统消息需要缓存，system 参数需要是 content blocks 格式。

        Args:
            messages: 消息列表
            system_prompt: 系统提示词

        Returns:
            (system, messages) - system 可能是字符串或 content blocks
        """
        system: str | list[dict[str, Any]] | None = system_prompt
        formatted_messages = []
        system_cache_control = None

        for msg in messages:
            if msg.get("role") == "system":
                # 提取系统消息
                system = msg.get("content", "")
                system_cache_control = msg.get("cache_control")
                continue

            formatted_msg: dict[str, Any] = {
                "role": msg.get("role"),
                "content": msg.get("content"),
            }

            formatted_messages.append(formatted_msg)

        # 如果系统消息需要缓存，转换为 content blocks 格式
        if system and system_cache_control:
            system = [
                {
                    "type": "text",
                    "text": system,
                    "cache_control": system_cache_control,
                }
            ]

        return system, formatted_messages

    def format_for_deepseek(
        self,
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        格式化消息为 DeepSeek API 格式

        DeepSeek 使用类似 Anthropic 的 cache_control 参数。
        注意：DeepSeek 只支持对 system 消息进行缓存。

        Args:
            messages: 消息列表

        Returns:
            格式化后的消息列表
        """
        formatted_messages = []

        for msg in messages:
            formatted_msg = msg.copy()

            # DeepSeek 的 cache_control 放在消息级别
            # 非系统消息移除 cache_control
            if "cache_control" in msg and msg.get("role") != "system":
                del formatted_msg["cache_control"]

            formatted_messages.append(formatted_msg)

        return formatted_messages

    def get_cache_stats(self) -> dict[str, Any]:
        """
        获取缓存统计

        Returns:
            包含缓存统计信息的字典
        """
        return {
            "hits": self._stats.hits,
            "misses": self._stats.misses,
            "hit_rate": self._stats.hit_rate,
            "cache_read_tokens": self._stats.cache_read_tokens,
            "cache_creation_tokens": self._stats.cache_creation_tokens,
            "estimated_savings": self._stats.estimated_savings,
        }

    def update_stats(
        self,
        usage: dict[str, int] | None,
        provider: str,
    ) -> None:
        """
        更新缓存统计

        根据 API 响应中的 usage 信息判断缓存命中情况。

        Args:
            usage: API 响应中的 usage 信息
            provider: 提供商名称
        """
        if not usage:
            return

        # Anthropic/DeepSeek 返回 cache_read_input_tokens
        cache_read = usage.get("cache_read_input_tokens", 0)
        cache_creation = usage.get("cache_creation_input_tokens", 0)

        if cache_read > 0:
            self._stats.hits += 1
            self._stats.cache_read_tokens += cache_read
            # 估算节省的成本
            config = self.PROVIDER_CACHE_CONFIG.get(provider, {})
            discount = config.get("discount", 0.5)
            savings = cache_read * (1 - discount)
            self._stats.estimated_savings += savings
            logger.info(
                "Cache hit! Read %d tokens from cache, saved ~%d token equivalents",
                cache_read,
                int(savings),
            )
        elif cache_creation > 0:
            self._stats.misses += 1
            self._stats.cache_creation_tokens += cache_creation
            logger.info("Cache miss, created cache with %d tokens", cache_creation)

    def reset_stats(self) -> None:
        """重置缓存统计"""
        self._stats = CacheStats()


# 全局缓存管理器实例
_prompt_cache_manager: PromptCacheManager | None = None


def get_prompt_cache_manager() -> PromptCacheManager:
    """
    获取全局缓存管理器

    Returns:
        PromptCacheManager 实例
    """
    global _prompt_cache_manager
    if _prompt_cache_manager is None:
        _prompt_cache_manager = PromptCacheManager()
    return _prompt_cache_manager
