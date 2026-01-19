"""
Core Interfaces - 核心层接口定义

定义 Core 层依赖的配置接口（使用 Python Protocol 实现结构化子类型）。
这些接口使 Core 层不直接依赖 app.config.Settings，遵循依赖倒置原则（DIP）。

命名约定：所有 Protocol 类以 `Protocol` 后缀结尾，明确标识其为接口定义。

使用方式：
    from core.interfaces import LLMConfigProtocol

    def create_gateway(config: LLMConfigProtocol) -> LLMGateway:
        # config 可以是任何符合 LLMConfigProtocol 结构的对象
        ...
"""

from typing import Protocol

from pydantic import SecretStr


class LLMConfigProtocol(Protocol):
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

    # Embedding 配置
    embedding_model: str

    # 调试配置
    debug: bool = False
    is_development: bool = False


class SandboxConfigProtocol(Protocol):
    """沙箱配置接口"""

    sandbox_enabled: bool
    sandbox_timeout: int
    sandbox_memory_limit: str
    sandbox_cpu_limit: float
    sandbox_network_mode: str
    work_dir: str


class MemoryConfigProtocol(Protocol):
    """记忆配置接口"""

    # 使用 LLMConfigProtocol 中的 API keys
    pass


class QualityConfigProtocol(Protocol):
    """代码质量配置接口"""

    # 使用 LLMConfigProtocol 中的 API keys
    pass


class AuthConfigProtocol(Protocol):
    """认证配置接口"""

    jwt_secret_key: str
    jwt_algorithm: str
    access_token_expire_minutes: int
    refresh_token_expire_days: int


class ImageGeneratorConfigProtocol(Protocol):
    """图像生成配置接口"""

    # 火山引擎配置
    volcengine_api_key: SecretStr | None
    volcengine_api_base: str
    volcengine_endpoint_id: str | None
    volcengine_image_endpoint_id: str | None

    # OpenAI 配置
    openai_api_key: SecretStr | None
    openai_api_base: str
