"""
Application Configuration Management

使用 Pydantic Settings 管理配置，支持环境变量和 .env 文件
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ========================================================================
    # 应用配置
    # ========================================================================
    app_name: str = "AI-Agent"
    app_env: Literal["development", "staging", "production"] = "development"
    debug: bool = True
    secret_key: SecretStr = Field(default=SecretStr("change-me-in-production"))
    api_prefix: str = "/api/v1"

    # ========================================================================
    # 服务器配置
    # ========================================================================
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 4
    reload: bool = True

    # ========================================================================
    # 数据库配置
    # ========================================================================
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ai_agent"
    database_pool_size: int = 20
    database_max_overflow: int = 10
    database_echo: bool = False

    # ========================================================================
    # Redis 配置
    # ========================================================================
    redis_url: str = "redis://localhost:6379/0"
    redis_password: str | None = None
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # ========================================================================
    # 向量数据库配置
    # ========================================================================
    vector_db_type: Literal["qdrant", "chroma"] = "qdrant"
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    chroma_path: str = "./data/chroma"

    # ========================================================================
    # 记忆存储配置
    # ========================================================================
    memory_store_type: Literal["postgres", "memory"] = "postgres"  # LangGraph Store 类型

    # ========================================================================
    # LLM 配置
    # ========================================================================
    # OpenAI
    openai_api_key: SecretStr | None = None
    openai_api_base: str = "https://api.openai.com/v1"

    # Anthropic (Claude)
    anthropic_api_key: SecretStr | None = None

    # 阿里云通义千问 (DashScope)
    dashscope_api_key: SecretStr | None = None
    dashscope_api_base: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    # DeepSeek
    deepseek_api_key: SecretStr | None = None
    deepseek_api_base: str = "https://api.deepseek.com"

    # 火山引擎 (字节跳动豆包)
    volcengine_api_key: SecretStr | None = None
    volcengine_api_base: str = "https://ark.cn-beijing.volces.com/api/v3"
    volcengine_endpoint_id: str | None = None  # 通用接入点 (兼容旧配置)
    volcengine_chat_endpoint_id: str | None = None  # 对话模型接入点 (Doubao-pro/lite)
    volcengine_image_endpoint_id: str | None = None  # 图像生成接入点 (Seedream)

    # 智谱AI (GLM)
    zhipuai_api_key: SecretStr | None = None
    zhipuai_api_base: str = "https://open.bigmodel.cn/api/paas/v4"  # 通用端点
    zhipuai_coding_api_base: str | None = None  # Coding端点（用于GLM-4.7编码套餐）

    # 本地模型 (Ollama)
    local_llm_url: str = "http://localhost:11434"

    # 默认模型配置
    # DeepSeek 支持的模型: deepseek-chat, deepseek-coder, deepseek-reasoner
    default_model: str = "deepseek-reasoner"
    embedding_model: str = "text-embedding-3-small"

    # ========================================================================
    # 安全配置
    # ========================================================================
    jwt_secret: SecretStr = Field(default=SecretStr("jwt-secret-change-in-production"))
    jwt_secret_key: str = "jwt-secret-change-in-production"  # 用于 JWT 编码
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 24
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:8000"]
    )

    # ========================================================================
    # 存储配置
    # ========================================================================
    storage_type: Literal["local", "s3", "minio"] = "local"
    storage_path: str = "./data/storage"
    s3_bucket: str = "ai-agent"
    s3_region: str = "us-east-1"
    s3_access_key: str | None = None
    s3_secret_key: SecretStr | None = None

    # ========================================================================
    # 工具沙箱配置
    # ========================================================================
    sandbox_enabled: bool = True
    sandbox_timeout: int = 60
    sandbox_memory_limit: str = "512m"
    sandbox_cpu_limit: float = 1.0
    sandbox_network_mode: str = "none"
    work_dir: str = "./workspace"

    # ========================================================================
    # Agent 执行配置
    # ========================================================================
    agent_max_iterations: int = 20
    agent_max_tokens: int = 100000
    agent_timeout_seconds: int = 600

    # Human-in-the-Loop 配置
    hitl_enabled: bool = True
    hitl_interrupt_tools: list[str] = Field(
        default_factory=lambda: ["run_shell", "write_file", "delete_file", "send_email"]
    )
    hitl_auto_approve_patterns: list[str] = Field(
        default_factory=lambda: ["read_*", "search_*", "list_*"]
    )

    # ========================================================================
    # 检查点配置
    # ========================================================================
    checkpoint_enabled: bool = True
    checkpoint_storage: Literal["redis", "postgres"] = "redis"
    checkpoint_ttl_days: int = 7

    # ========================================================================
    # 日志配置
    # ========================================================================
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_format: Literal["json", "text"] = "json"
    log_file: str | None = None

    # ========================================================================
    # 监控配置
    # ========================================================================
    metrics_enabled: bool = True
    tracing_enabled: bool = False
    jaeger_endpoint: str | None = None

    @property
    def is_development(self) -> bool:
        """是否为开发环境"""
        return self.app_env == "development"

    @property
    def is_production(self) -> bool:
        """是否为生产环境"""
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()


# 全局配置实例
settings = get_settings()
