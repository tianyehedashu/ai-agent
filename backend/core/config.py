"""
Core Configuration - 核心配置接口

定义 Core 层需要的配置接口，避免依赖应用层配置
"""

from typing import Protocol

from pydantic import SecretStr


class LLMConfig(Protocol):
    """LLM 配置接口"""

    # API Keys
    anthropic_api_key: SecretStr | None
    openai_api_key: SecretStr | None
    dashscope_api_key: SecretStr | None
    deepseek_api_key: SecretStr | None
    volcengine_api_key: SecretStr | None
    zhipuai_api_key: SecretStr | None

    # API Bases
    openai_api_base: str
    dashscope_api_base: str
    deepseek_api_base: str
    volcengine_api_base: str
    zhipuai_api_base: str

    # 火山引擎配置
    volcengine_endpoint_id: str | None
    volcengine_chat_endpoint_id: str | None
    volcengine_image_endpoint_id: str | None

    # 默认模型
    default_model: str

    # 调试配置
    debug: bool = False
    is_development: bool = False


class SandboxConfig(Protocol):
    """沙箱配置接口"""

    sandbox_enabled: bool
    sandbox_timeout: int
    sandbox_memory_limit: str
    sandbox_cpu_limit: float
    sandbox_network_mode: str
    work_dir: str


class MemoryConfig(Protocol):
    """记忆配置接口"""

    # 使用 LLMConfig 中的 API keys
    pass


class QualityConfig(Protocol):
    """代码质量配置接口"""

    # 使用 LLMConfig 中的 API keys
    pass


class AuthConfig(Protocol):
    """认证配置接口"""

    jwt_secret_key: str
    jwt_algorithm: str
    access_token_expire_minutes: int
    refresh_token_expire_days: int


class ImageGeneratorConfig(Protocol):
    """图像生成配置接口"""

    # 火山引擎配置
    volcengine_api_key: SecretStr | None
    volcengine_api_base: str
    volcengine_endpoint_id: str | None
    volcengine_image_endpoint_id: str | None

    # OpenAI 配置
    openai_api_key: SecretStr | None
    openai_api_base: str
