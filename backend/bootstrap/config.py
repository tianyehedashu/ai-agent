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
import uuid

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from bootstrap.config_loader import app_config
from domains.gateway.domain.provider_api_base import get_default_api_base


def _default_provider_api_base(provider: str) -> str:
    """Settings 字段默认 base；权威定义在 ``domain/provider_api_base``。"""
    base = get_default_api_base(provider)
    if base is None:
        msg = f"provider {provider!r} has no default api_base for Settings"
        raise ValueError(msg)
    return base


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
    root_path: str = "/ai-agent"  # 服务级前缀（环境变量 ROOT_PATH；设为空字符串可关闭）
    cookie_secure: bool | None = None  # None = 自动（生产 HTTPS 时 True）；内网 HTTP 部署设为 False

    @field_validator("root_path", mode="before")
    @classmethod
    def normalize_root_path(cls, value: object) -> object:
        """去除 ROOT_PATH 首尾空白，避免 Secret/.env 误写空格导致路由 404。"""
        if isinstance(value, str):
            return value.strip()
        return value

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
    # 后台任务专用连接池（不抢热路径连接）
    database_background_pool_size: int = 4
    database_background_max_overflow: int = 2

    # ========================================================================
    # Redis 配置
    # ========================================================================
    redis_url: str = "redis://localhost:6379/0"
    # 与 giikin-iam 共用阿里云 Redis 时须与 Nacos spring.data.redis 一致（含 username）
    redis_username: str | None = None
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
    openai_api_base: str = Field(default_factory=lambda: _default_provider_api_base("openai"))

    # Anthropic (Claude)
    anthropic_api_key: SecretStr | None = None

    # 阿里云通义千问 (DashScope)
    dashscope_api_key: SecretStr | None = None
    dashscope_api_base: str = Field(default_factory=lambda: _default_provider_api_base("dashscope"))

    # DeepSeek
    deepseek_api_key: SecretStr | None = None
    deepseek_api_base: str = Field(default_factory=lambda: _default_provider_api_base("deepseek"))

    # 火山引擎 (字节跳动豆包)
    volcengine_api_key: SecretStr | None = None
    volcengine_api_base: str = Field(
        default_factory=lambda: _default_provider_api_base("volcengine")
    )
    volcengine_endpoint_id: str | None = None  # 通用接入点 (兼容旧配置)
    volcengine_chat_endpoint_id: str | None = None  # 对话模型接入点 (Doubao-pro/lite)
    volcengine_image_endpoint_id: str | None = None  # 图像生成接入点 (Seedream)

    # 智谱AI (GLM) — 默认 base 见 domains/gateway/domain/provider_api_base.py
    zhipuai_api_key: SecretStr | None = None
    zhipuai_api_base: str = Field(default_factory=lambda: _default_provider_api_base("zhipuai"))

    # 本地模型 (Ollama)
    local_llm_url: str = "http://localhost:11434"

    # GIIKIN 视频生成 API
    giikin_client_id: str | None = None
    giikin_client_secret: str | None = None
    giikin_base_url: str = "https://openapi.giikin.com"
    giikin_creator_id: int | None = None  # 操作用户 ID，用于厂商追踪

    # ==========================================================================
    # 场景化模型配置（环境变量；空值时由 Gateway 可见目录兜底）
    # ==========================================================================
    default_model: str = Field(
        default="",
        validation_alias=AliasChoices("DEFAULT_MODEL"),
    )
    fast_model: str = Field(
        default="",
        validation_alias=AliasChoices("FAST_MODEL"),
    )
    reasoning_model: str = Field(
        default="",
        validation_alias=AliasChoices("REASONING_MODEL"),
    )
    code_model: str = Field(
        default="",
        validation_alias=AliasChoices("CODE_MODEL"),
    )
    long_context_model: str = Field(
        default="",
        validation_alias=AliasChoices("LONG_CONTEXT_MODEL"),
    )
    vision_model: str = Field(
        default="",
        validation_alias=AliasChoices("VISION_MODEL"),
    )

    # ==========================================================================
    # Embedding 配置（环境变量）
    # ==========================================================================
    embedding_provider: Literal["api", "local"] = Field(
        default="api",
        validation_alias=AliasChoices("EMBEDDING_PROVIDER"),
    )
    embedding_model: str = Field(
        default="",
        validation_alias=AliasChoices("EMBEDDING_MODEL"),
    )
    embedding_dimension: int = Field(
        default=1024,
        validation_alias=AliasChoices("EMBEDDING_DIMENSION"),
    )

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

    # ========================================================================
    # 外部联邦身份（可选；OIDC / introspection 等为适配器，见 libs/iam/federation）
    # ========================================================================
    federation_mode: Literal["none", "oidc", "oauth2_introspection"] = "none"
    oidc_issuer_url: str | None = None
    oidc_audience: str | None = None
    oauth2_introspection_url: str | None = None

    # ========================================================================
    # 认证模式
    #   sso    - 生产：信任 HiGress(giikin-auth-bridge) 注入的 X-Giikin-* 身份 Header，
    #            校验 X-Giikin-Internal-Key，并按 giikin user_id JIT 建本地用户
    #   local  - 本地/开发：走 ai-agent 自身的邮箱密码 + JWT 登录
    #   hybrid - 双通道：同时支持 SSO 与邮箱密码登录；Bearer JWT 优先，无 Bearer 才走网关 Header
    # ========================================================================
    auth_mode: Literal["sso", "local", "hybrid"] = "local"
    # 与 HiGress giikin-auth-bridge 的 internal_key 对齐。
    # sso 模式下必填（fail-closed）：缺失则任何绕过网关的直连都能伪造 X-Giikin-* 身份。
    giikin_internal_key: SecretStr | None = None
    # HiGress 注入的身份 Header 名（与 giikin-auth-bridge InjectHeaders 一致）
    giikin_user_json_header: str = "X-Giikin-User-JSON"
    giikin_user_id_header: str = "X-Giikin-User-Id"
    giikin_internal_key_header: str = "X-Giikin-Internal-Key"
    # 与 giikin-iam UserActionListener 下发的 Cookie 名一致（仅 cookie 回退模式使用）
    giikin_session_cookie_name: str = "guard_token"
    # 生产应关闭：身份由 HiGress giikin-auth-bridge 注入 Header，不应由 backend 直连 IAM Redis
    giikin_session_cookie_fallback: bool = False
    # 是否允许公开注册（hybrid/local 模式下可关闭，仅管理员创建账号）
    allow_register: bool = True

    @property
    def is_sso_auth(self) -> bool:
        """是否启用 giikin 网关 SSO 认证模式。"""
        return self.auth_mode == "sso"

    @property
    def is_hybrid_auth(self) -> bool:
        """是否启用双通道认证模式（SSO + 本地邮箱密码）。"""
        return self.auth_mode == "hybrid"

    @property
    def is_sso_capable(self) -> bool:
        """是否具备 SSO 能力（sso 或 hybrid）。"""
        return self.auth_mode in ("sso", "hybrid")

    def model_post_init(self, __context: object) -> None:  # pylint: disable=arguments-differ
        """初始化后处理：如果 jwt_secret_key 是默认值，则使用 jwt_secret 的值"""
        super().model_post_init(__context)
        # 如果 jwt_secret_key 仍然是默认值，且 jwt_secret 不是默认值，则使用 jwt_secret 的值
        if (
            self.jwt_secret_key == "jwt-secret-change-in-production"
            and self.jwt_secret.get_secret_value() != "jwt-secret-change-in-production"
        ):
            self.jwt_secret_key = self.jwt_secret.get_secret_value()

        # fail-closed：SSO / hybrid 模式必须配置 internal_key，否则可被绕过网关伪造身份
        if self.auth_mode in ("sso", "hybrid") and (
            self.giikin_internal_key is None
            or not self.giikin_internal_key.get_secret_value().strip()
        ):
            msg = (
                f"auth_mode='{self.auth_mode}' requires giikin_internal_key to be set "
                "(防止绕过 HiGress 直连伪造 X-Giikin-* 身份)"
            )
            raise ValueError(msg)

    # ========================================================================
    # 存储配置（已废弃：业务真源为 system_storage_config 表 + /admin/storage）
    # ========================================================================
    storage_type: Literal["local", "s3", "minio"] = "local"  # deprecated
    storage_path: str = "./data/storage"  # deprecated
    s3_bucket: str = "ai-agent"  # deprecated
    s3_region: str = "us-east-1"  # deprecated
    s3_access_key: str | None = None  # deprecated
    s3_secret_key: SecretStr | None = None  # deprecated

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

    # ========================================================================
    # AI Gateway 配置
    # ========================================================================
    # 启动时是否从 gateway-catalog.seed.json 跑完整目录维护（含 DB 写入 + 审计 + Router 重载）
    # 默认 False：代理调用每次注入下游/上游单价至 metadata，``litellm.model_cost`` 内置项已足够兜底，
    # DB 行的 LiteLLM 注册随管理面写入路径增量进行（``PricingService.sync_to_litellm_registry``）。
    gateway_catalog_sync_on_startup: bool = False
    # 同步时是否用配置覆盖 tags（GitOps：配置声明优先于 UI 对托管行的修改）
    gateway_catalog_config_overwrites_managed: bool = True
    # 配置移除某托管模型后是否从各 vkey 的 allowed_models 中剔除该虚拟名（False=不修改白名单）
    gateway_catalog_prune_vkey_allowed_models: bool = False
    # system vkey 是否禁止在 Router 无部署时走 LiteLLM 直连兜底（True=强制经 Router，便于统计一致）
    gateway_proxy_disable_internal_direct_litellm: bool = True
    # DashScope embedding 经 LiteLLM Router/aembedding（默认 False=兼容端点直连）
    gateway_dashscope_embedding_via_litellm: bool = False
    # 文档化版本门槛（可选；probe 脚本可读取）
    gateway_dashscope_embedding_litellm_min_version: str | None = None
    # 无 PermissionContext.user_id 时用于 Gateway 归因的委派用户（如系统账号 UUID）
    gateway_internal_proxy_delegate_user_id: uuid.UUID | None = None
    # 是否在 LiteLLM 注册 PII Guardrail 回调（False=暂不启用；True 时仍受 vkey.guardrail_enabled 控制）
    gateway_default_guardrail_enabled: bool = False
    # Anthropic-native 出站直通：True 时 ``gateway_models.upstream_call_shape='anthropic_native'``
    # 或 profile.default_call_shape=anthropic_native 的 deployment 会用 Anthropic 通道
    # （``model='anthropic/...'`` + profile 的 Anthropic-native 根）。
    gateway_enable_anthropic_native_passthrough: bool = True
    # 默认是否在日志中存完整 prompt/response（vkey 可覆盖）
    gateway_default_store_full_messages: bool = False
    # 上游 LLM 调用总超时（秒）。大模型推理可能较慢（如 extended thinking 100s+），
    # 默认 300s 覆盖绝大部分场景；视频/图像生成因耗时更长建议通过环境变量单独调大。
    # 设为 0 关闭超时（仅调试时使用）。
    gateway_upstream_timeout_seconds: int = Field(default=300, ge=0)
    # 流式调用每个 chunk 间最大等待时间（秒）。上游若在此时间内未产出任何 chunk，
    # 视为连接断开。基于 LiteLLM stream_timeout，默认 60s。
    gateway_upstream_stream_timeout_seconds: int = Field(default=60, ge=0)
    # Router 启用 cooldown 的失败次数阈值（与 LiteLLM 默认一致）
    gateway_router_cooldown_threshold: int = 5
    # Router 单次 cooldown 时长（秒）
    gateway_router_cooldown_seconds: int = 60
    # 跨进程 cooldown / TPM-RPM 共享 Redis URL（默认复用主 redis）
    gateway_router_redis_url: str | None = None
    # 热路径：``resolve_model_or_route`` 进程内 LRU+TTL（管理面写路径会失效）
    gateway_resolve_model_cache_enabled: bool = True
    # 热路径：``TeamService.get_team`` / ``member_role`` 进程内短 TTL
    gateway_team_cache_enabled: bool = True
    # SQLAlchemy 慢查询日志阈值（毫秒）；0 = 关闭
    gateway_slow_sql_threshold_ms: int = Field(default=50, ge=0)
    # rollup 任务间隔（秒）
    gateway_rollup_interval_seconds: int = 300
    # 告警检查间隔（秒）
    gateway_alert_interval_seconds: int = 60
    # 月分区维护间隔（秒）
    gateway_partition_interval_seconds: int = 86400
    # 请求明细表按月分区：保留最近 N 天以外的整月分区将自动 DROP；None=不自动删除
    gateway_request_log_retention_days: int | None = None
    # 过期分区清理任务间隔（秒）
    gateway_request_log_retention_interval_seconds: int = 86400
    # 成功请求写入明细的采样率 0.0~1.0（1.0=全量）；低于 1 时 ``gateway_metrics_hourly`` 与基于日志的告警可能低估成功量
    gateway_request_log_success_sample_rate: float = Field(default=1.0, ge=0.0, le=1.0)
    # 非 success 是否始终写明细
    gateway_request_log_always_persist_non_success: bool = True
    # 成功请求 cost(USD) 不低于该阈值时始终写明细；None=不按金额
    gateway_request_log_always_persist_cost_above_usd: float | None = None
    # 详细请求日志：提示词摘要最大字符（硬上限）
    gateway_request_log_prompt_max_chars: int = Field(default=4096, ge=256, le=65536)
    # 非详细模式：响应 preview 最大字符（与历史 ~200 对齐）
    gateway_request_log_response_preview_max_chars: int = Field(default=200, ge=0, le=8192)
    # 详细模式（store_full_messages / 会话或请求开关）：assistant 正文 preview 上限
    gateway_request_log_response_verbose_max_chars: int = Field(default=16384, ge=0, le=65536)
    # tool_calls 摘要 JSON 最大字符
    gateway_request_log_tool_calls_summary_max_chars: int = Field(default=2000, ge=0, le=8192)
    # Chat 请求体中的 gateway_verbose_request_log 是否生效（生产建议 False）
    gateway_allow_client_request_verbose_log: bool = False
    # USD → CNY 展示汇率（存储仍为 USD）
    gateway_fx_usd_cny: float = Field(default=7.20, gt=0)
    gateway_display_default_currency: str = "CNY"

    @property
    def is_development(self) -> bool:
        """是否为开发环境"""
        return self.app_env == "development"

    @property
    def is_production(self) -> bool:
        """是否为生产环境"""
        return self.app_env == "production"

    @property
    def is_cookie_secure(self) -> bool:
        """Cookie 是否要求 HTTPS。显式设置时使用配置值，否则非开发环境默认 True。"""
        if self.cookie_secure is not None:
            return self.cookie_secure
        return not self.is_development


@lru_cache
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()


# 全局配置实例
settings = get_settings()
