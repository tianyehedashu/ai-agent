"""
LLM Key Service 配置适配器

将 bootstrap.config.Settings（或任意实现 libs.config.interfaces.LLMConfigProtocol 的对象）
适配为 LLMKeyService 所需的 LLMConfigProtocol（get_provider_api_key(provider)、get_provider_api_base(provider)、default_daily_*）。
"""

from typing import Protocol

from libs.config.interfaces import LLMConfigProtocol as SettingsLLMConfigProtocol


class LLMKeyServiceConfigProtocol(Protocol):
    """LLMKeyService 所需的配置协议"""

    def get_provider_api_key(self, provider: str) -> str | None:
        """获取提供商的系统 API Key"""
        ...

    def get_provider_api_base(self, provider: str) -> str | None:
        """获取提供商的 API Base"""
        ...

    @property
    def default_daily_text_requests(self) -> int:
        """默认每日文本请求数"""
        ...

    @property
    def default_daily_image_requests(self) -> int:
        """默认每日图像请求数"""
        ...

    @property
    def default_daily_embedding_requests(self) -> int:
        """默认每日 Embedding 请求数"""
        ...


# 提供商名称到 Settings 属性的映射
_PROVIDER_KEY_ATTR: dict[str, str] = {
    "openai": "openai_api_key",
    "anthropic": "anthropic_api_key",
    "dashscope": "dashscope_api_key",
    "deepseek": "deepseek_api_key",
    "volcengine": "volcengine_api_key",
    "zhipuai": "zhipuai_api_key",
}

_PROVIDER_BASE_ATTR: dict[str, str] = {
    "openai": "openai_api_base",
    "anthropic": "anthropic_api_base",  # Anthropic 无 base 通常用默认
    "dashscope": "dashscope_api_base",
    "deepseek": "deepseek_api_base",
    "volcengine": "volcengine_api_base",
    "zhipuai": "zhipuai_api_base",
}


class LLMKeyServiceConfigAdapter:
    """将 Settings 适配为 LLMKeyService 的 config"""

    def __init__(
        self,
        settings: SettingsLLMConfigProtocol,
        default_daily_text: int = 100,
        default_daily_image: int = 10,
        default_daily_embedding: int = 50,
    ):
        self._settings = settings
        self._default_daily_text = default_daily_text
        self._default_daily_image = default_daily_image
        self._default_daily_embedding = default_daily_embedding

    def get_provider_api_key(self, provider: str) -> str | None:
        """根据提供商名称返回系统 API Key"""
        attr = _PROVIDER_KEY_ATTR.get(provider)
        if not attr:
            return None
        key = getattr(self._settings, attr, None)
        if key is None:
            return None
        return key.get_secret_value()

    def get_provider_api_base(self, provider: str) -> str | None:
        """根据提供商名称返回 API Base"""
        attr = _PROVIDER_BASE_ATTR.get(provider)
        if not attr:
            return None
        base = getattr(self._settings, attr, None)
        if isinstance(base, str) and base:
            return base
        return None

    @property
    def default_daily_text_requests(self) -> int:
        return self._default_daily_text

    @property
    def default_daily_image_requests(self) -> int:
        return self._default_daily_image

    @property
    def default_daily_embedding_requests(self) -> int:
        return self._default_daily_embedding


def create_llm_key_service_config(
    settings: SettingsLLMConfigProtocol,
    default_daily_text: int = 100,
    default_daily_image: int = 10,
    default_daily_embedding: int = 50,
) -> LLMKeyServiceConfigAdapter:
    """创建 LLMKeyService 用的配置适配器"""
    return LLMKeyServiceConfigAdapter(
        settings,
        default_daily_text=default_daily_text,
        default_daily_image=default_daily_image,
        default_daily_embedding=default_daily_embedding,
    )
