"""
Application Configuration Management

配置优先级（从高到低）：
1. 环境变量（最高优先级）
2. .env 文件
3. config/app.toml 文件
4. 代码中的默认值

敏感信息（API Keys、密码）放在 .env 文件
应用逻辑配置（功能开关、模型列表）放在 config/app.toml
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from bootstrap.config_loader import app_config


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

    # ==========================================================================
    # 场景化模型配置（从 config/app.toml 加载）
    # ==========================================================================
    # 模型名称格式: provider/model_name (如 deepseek/deepseek-chat)

    # 默认对话模型
    default_model: str = Field(default_factory=lambda: app_config.llm.default_model)

    # 快速响应模型（用于简单任务、工具调用前的意图识别等）
    fast_model: str = Field(default_factory=lambda: app_config.llm.fast_model)

    # 复杂推理模型（数学、逻辑、代码分析等）
    reasoning_model: str = Field(default_factory=lambda: app_config.llm.reasoning_model)

    # 代码生成模型
    code_model: str = Field(default_factory=lambda: app_config.llm.code_model)

    # 长文档处理模型
    long_context_model: str = Field(default_factory=lambda: app_config.llm.long_context_model)

    # 视觉理解模型
    vision_model: str = Field(default_factory=lambda: app_config.llm.vision_model)

    # ==========================================================================
    # Embedding 配置（从 config/app.toml 加载）
    # ==========================================================================
    # provider: "api"（云端 API）或 "local"（本地模型，CPU 友好）
    embedding_provider: Literal["api", "local"] = Field(
        default_factory=lambda: app_config.llm.embedding_provider  # type: ignore
    )
    # API 模式模型: text-embedding-3-small, doubao-embedding-* 等
    # 本地模式模型: bge-small-zh, bge-base-en 或完整名称如 BAAI/bge-small-zh-v1.5
    embedding_model: str = Field(default_factory=lambda: app_config.llm.embedding_model)
    # 向量维度（不同模型维度不同）
    # API: text-embedding-3-small=1536, text-embedding-3-large=3072
    # 本地: bge-small-zh=512, bge-base-zh=768, bge-m3=1024
    embedding_dimension: int = Field(default_factory=lambda: app_config.llm.embedding_dimension)

    # ========================================================================
    # 安全配置
    # ========================================================================
    jwt_secret: SecretStr = Field(default=SecretStr("jwt-secret-change-in-production"))
    jwt_secret_key: str = Field(
        default="jwt-secret-change-in-production",
        description="JWT 密钥（用于 JWT 编码），如果未设置 JWT_SECRET_KEY，则使用 jwt_secret 的值",
    )
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 24
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:8000"]
    )

    def model_post_init(self, __context: object) -> None:
        """初始化后处理：如果 jwt_secret_key 是默认值，则使用 jwt_secret 的值"""
        super().model_post_init(__context)
        # 如果 jwt_secret_key 仍然是默认值，且 jwt_secret 不是默认值，则使用 jwt_secret 的值
        if (
            self.jwt_secret_key == "jwt-secret-change-in-production"
            and self.jwt_secret.get_secret_value() != "jwt-secret-change-in-production"
        ):
            self.jwt_secret_key = self.jwt_secret.get_secret_value()

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
    work_dir: str = "/tmp/workspace"  # 临时工作目录，仅在 Local 模式下使用

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
    # Token 优化配置
    # ========================================================================
    # 提示词缓存（Prompt Caching）
    # 这是 2026 年最有效的 Token 成本优化手段，可节省 50%-90%
    prompt_cache_enabled: bool = True

    # 记忆摘要（Summarization）
    # 当对话 Token 超过阈值时自动触发摘要，可节省 40%-70%
    memory_summarization_enabled: bool = True
    memory_summarization_threshold: int = 8000  # Token 阈值
    memory_summarization_preserve_recent: int = 4  # 保留最近 N 条消息

    # 分层记忆（Tiered Memory）
    # 分离工作记忆、短期记忆、长期记忆
    tiered_memory_enabled: bool = True
    short_term_memory_ttl_hours: int = 24
    long_term_importance_threshold: float = 6.0

    # ========================================================================
    # SimpleMem 配置（会话内长程记忆）
    # ========================================================================
    # SimpleMem 提供 30x Token 压缩和 26.4% F1 提升
    # 详细配置见 config/app.toml [simplemem] 部分
    # 环境变量可覆盖 TOML 配置
    simplemem_enabled: bool = Field(default_factory=lambda: app_config.simplemem.enabled)
    simplemem_extraction_model: str | None = Field(
        default_factory=lambda: app_config.simplemem.extraction_model
    )
    simplemem_window_size: int = Field(default_factory=lambda: app_config.simplemem.window.size)
    simplemem_novelty_threshold: float = Field(
        default_factory=lambda: app_config.simplemem.filter.novelty_threshold
    )
    simplemem_skip_trivial: bool = Field(
        default_factory=lambda: app_config.simplemem.filter.skip_trivial
    )

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
