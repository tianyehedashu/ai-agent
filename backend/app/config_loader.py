"""
TOML 配置加载器

支持 TOML + 环境变量 统一配置方案：
- TOML 中可使用 ${VAR} 或 ${VAR:default} 引用环境变量
- 敏感信息通过 .env 加载到环境变量，再由 TOML 引用
- 实现配置的统一管理和可视化

使用方式：
    from app.config_loader import app_config

    # 访问 SimpleMem 配置
    if app_config.simplemem.enabled:
        model = app_config.simplemem.extraction_model

    # 访问模型列表
    for model in app_config.models.available:
        print(f"{model.name}: ${model.input_price}/1M tokens")

环境变量插值语法：
    ${VAR}           - 引用环境变量，不存在则为空
    ${VAR:default}   - 引用环境变量，不存在则使用默认值
"""

from dataclasses import dataclass, field
from functools import lru_cache
import logging
import os
from pathlib import Path
import re
import tomllib
from typing import Any

# 注意：config_loader 是最底层模块，不能依赖 utils/logging（会导致循环依赖）
# 直接使用标准 logging
logger = logging.getLogger(__name__)


# =============================================================================
# SimpleMem 配置
# =============================================================================


@dataclass
class SimpleMemWindowConfig:
    """滑动窗口配置"""

    size: int = 10
    stride: int = 5


@dataclass
class SimpleMemFilterConfig:
    """信息密度过滤配置"""

    novelty_threshold: float = 0.35
    min_content_length: int = 20
    skip_trivial: bool = True


@dataclass
class SimpleMemRetrievalConfig:
    """自适应检索配置"""

    k_min: int = 3
    k_max: int = 15
    complexity_threshold: float = 0.5


@dataclass
class SimpleMemConsolidationConfig:
    """记忆合并配置"""

    interval: int = 50


@dataclass
class SimpleMemConfig:
    """SimpleMem 完整配置"""

    enabled: bool = True
    extraction_model: str = "gpt-4o-mini"
    window: SimpleMemWindowConfig = field(default_factory=SimpleMemWindowConfig)
    filter: SimpleMemFilterConfig = field(default_factory=SimpleMemFilterConfig)
    retrieval: SimpleMemRetrievalConfig = field(default_factory=SimpleMemRetrievalConfig)
    consolidation: SimpleMemConsolidationConfig = field(
        default_factory=SimpleMemConsolidationConfig
    )


# =============================================================================
# 模型配置
# =============================================================================


@dataclass
class ModelInfo:
    """单个模型信息"""

    id: str
    name: str
    provider: str
    context_window: int = 128000
    input_price: float = 0.0  # $/1M tokens 或 ¥/千tokens（根据提供商）
    output_price: float = 0.0
    supports_vision: bool = False
    supports_tools: bool = True
    supports_reasoning: bool = False  # 是否支持推理/思维链
    litellm_model: str = ""  # LiteLLM 调用格式 (如 deepseek/deepseek-chat)
    recommended_for: list[str] = field(default_factory=list)  # 推荐使用场景
    description: str = ""  # 模型描述


@dataclass
class ModelsConfig:
    """模型配置"""

    default: str = "deepseek/deepseek-chat"
    embedding: str = "text-embedding-3-small"
    available: list[ModelInfo] = field(default_factory=list)

    def get_model(self, model_id: str) -> ModelInfo | None:
        """根据 ID 获取模型信息"""
        for model in self.available:
            if model.id == model_id:
                return model
        return None

    def get_models_by_provider(self, provider: str) -> list[ModelInfo]:
        """获取指定提供商的所有模型"""
        return [m for m in self.available if m.provider == provider]

    def get_vision_models(self) -> list[ModelInfo]:
        """获取支持视觉的模型"""
        return [m for m in self.available if m.supports_vision]

    def get_tool_models(self) -> list[ModelInfo]:
        """获取支持工具调用的模型"""
        return [m for m in self.available if m.supports_tools]

    def get_reasoning_models(self) -> list[ModelInfo]:
        """获取支持推理的模型"""
        return [m for m in self.available if m.supports_reasoning]

    def get_models_for_scene(self, scene: str) -> list[ModelInfo]:
        """获取推荐用于特定场景的模型

        Args:
            scene: 场景名称，如 'code', 'reasoning', 'fast', 'vision', 'general' 等

        Returns:
            推荐的模型列表
        """
        return [m for m in self.available if scene in m.recommended_for]


# =============================================================================
# Agent 配置
# =============================================================================


@dataclass
class HITLConfig:
    """Human-in-the-Loop 配置"""

    enabled: bool = True
    interrupt_tools: list[str] = field(
        default_factory=lambda: ["run_shell", "write_file", "delete_file", "send_email"]
    )
    auto_approve_patterns: list[str] = field(
        default_factory=lambda: ["read_*", "search_*", "list_*"]
    )


@dataclass
class AgentConfig:
    """Agent 执行配置"""

    max_iterations: int = 20
    max_tokens: int = 100000
    timeout_seconds: int = 600
    hitl: HITLConfig = field(default_factory=HITLConfig)


# =============================================================================
# 检查点配置
# =============================================================================


@dataclass
class CheckpointConfig:
    """检查点配置"""

    enabled: bool = True
    storage: str = "redis"
    ttl_days: int = 7


# =============================================================================
# Token 优化配置
# =============================================================================


@dataclass
class SummarizationConfig:
    """记忆摘要配置"""

    enabled: bool = True
    threshold: int = 8000
    preserve_recent: int = 4


@dataclass
class TieredMemoryConfig:
    """分层记忆配置"""

    enabled: bool = True
    short_term_ttl_hours: int = 24
    long_term_importance_threshold: float = 6.0


@dataclass
class TokenOptimizationConfig:
    """Token 优化配置"""

    prompt_cache_enabled: bool = True
    summarization: SummarizationConfig = field(default_factory=SummarizationConfig)
    tiered_memory: TieredMemoryConfig = field(default_factory=TieredMemoryConfig)


# =============================================================================
# 日志和监控配置
# =============================================================================


@dataclass
class LoggingConfig:
    """日志配置"""

    level: str = "INFO"
    format: str = "json"
    file: str | None = None


@dataclass
class MonitoringConfig:
    """监控配置"""

    metrics_enabled: bool = True
    tracing_enabled: bool = False
    jaeger_endpoint: str | None = None


# =============================================================================
# 基础设施配置
# =============================================================================


@dataclass
class InfraConfig:
    """基础设施配置（数据库、Redis、向量库）"""

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ai_agent"
    redis_url: str = "redis://localhost:6379/0"
    vector_db_type: str = "qdrant"
    qdrant_url: str = "http://localhost:6333"


# =============================================================================
# LLM 提供商配置
# =============================================================================


@dataclass
class LLMProviderConfig:
    """单个 LLM 提供商配置"""

    api_key: str = ""
    api_base: str = ""


@dataclass
class VolcengineConfig:
    """火山引擎配置"""

    api_key: str = ""
    api_base: str = "https://ark.cn-beijing.volces.com/api/v3"
    chat_endpoint_id: str = ""


@dataclass
class LocalLLMConfig:
    """本地模型配置"""

    url: str = "http://localhost:11434"


@dataclass
class LLMConfig:
    """LLM 配置"""

    # ==========================================================================
    # 场景化模型配置
    # ==========================================================================
    # 默认对话模型
    default_model: str = "deepseek/deepseek-chat"
    # 快速响应模型（用于简单任务、工具调用前的意图识别等）
    fast_model: str = "dashscope/qwen-turbo"
    # 复杂推理模型（数学、逻辑、代码分析等）
    reasoning_model: str = "deepseek/deepseek-reasoner"
    # 代码生成模型
    code_model: str = "dashscope/qwen2.5-coder-32b-instruct"
    # 长文档处理模型（超过 100K token 的文档）
    long_context_model: str = "zai/glm-4-long"
    # 视觉理解模型
    vision_model: str = "dashscope/qwen-vl-max"

    # ==========================================================================
    # Embedding 配置
    # ==========================================================================
    embedding_provider: str = "api"  # "api" 或 "local"
    embedding_model: str = "text-embedding-3-small"
    # Embedding 向量维度（不同模型维度不同）
    # text-embedding-3-small: 1536, text-embedding-3-large: 3072
    # bge-small-zh: 512, bge-base-zh: 768, bge-m3: 1024
    embedding_dimension: int = 1536

    # ==========================================================================
    # LLM 提供商配置
    # ==========================================================================
    openai: LLMProviderConfig = field(default_factory=LLMProviderConfig)
    deepseek: LLMProviderConfig = field(default_factory=LLMProviderConfig)
    anthropic: LLMProviderConfig = field(default_factory=LLMProviderConfig)
    dashscope: LLMProviderConfig = field(default_factory=LLMProviderConfig)
    zhipuai: LLMProviderConfig = field(default_factory=LLMProviderConfig)
    volcengine: VolcengineConfig = field(default_factory=VolcengineConfig)
    local: LocalLLMConfig = field(default_factory=LocalLLMConfig)


# =============================================================================
# 应用配置（根配置）
# =============================================================================


@dataclass
class AppConfig:
    """应用配置（TOML 加载）"""

    # 基础设施（引用环境变量）
    infra: InfraConfig = field(default_factory=InfraConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)

    # 应用逻辑配置
    simplemem: SimpleMemConfig = field(default_factory=SimpleMemConfig)
    models: ModelsConfig = field(default_factory=ModelsConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    checkpoint: CheckpointConfig = field(default_factory=CheckpointConfig)
    token_optimization: TokenOptimizationConfig = field(default_factory=TokenOptimizationConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)


# =============================================================================
# 配置加载
# =============================================================================


def _dict_to_dataclass(cls: type, data: dict[str, Any]) -> Any:
    """递归将字典转换为 dataclass"""
    if not data:
        return cls()

    # 获取 dataclass 字段信息
    field_types = {}
    if hasattr(cls, "__dataclass_fields__"):
        field_types = {name: field.type for name, field in cls.__dataclass_fields__.items()}

    kwargs = {}
    for key, value in data.items():
        if key not in field_types:
            continue

        field_type = field_types[key]

        # 处理嵌套 dataclass
        if isinstance(value, dict) and hasattr(field_type, "__dataclass_fields__"):
            kwargs[key] = _dict_to_dataclass(field_type, value)
        # 处理列表（如 models.available）
        elif isinstance(value, list):
            # 尝试获取列表元素类型
            origin = getattr(field_type, "__origin__", None)
            if origin is list:
                args = getattr(field_type, "__args__", ())
                if args and hasattr(args[0], "__dataclass_fields__"):
                    kwargs[key] = [_dict_to_dataclass(args[0], item) for item in value]
                else:
                    kwargs[key] = value
            else:
                kwargs[key] = value
        else:
            kwargs[key] = value

    return cls(**kwargs)


def _deep_merge(base: dict, override: dict) -> dict:
    """深度合并两个字典，override 覆盖 base"""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


# 环境变量插值正则：${VAR} 或 ${VAR:default}
_ENV_VAR_PATTERN = re.compile(r"\$\{([^}:]+)(?::([^}]*))?\}")


def _resolve_env_vars(value: Any) -> Any:
    """递归解析配置值中的环境变量引用

    支持语法：
    - ${VAR}         - 引用环境变量，不存在则为空字符串
    - ${VAR:default} - 引用环境变量，不存在则使用默认值

    Args:
        value: 配置值（可以是字符串、字典、列表）

    Returns:
        解析后的值
    """
    if isinstance(value, str):

        def replace_env(match: re.Match) -> str:
            var_name = match.group(1)
            default = match.group(2) if match.group(2) is not None else ""
            return os.getenv(var_name, default)

        return _ENV_VAR_PATTERN.sub(replace_env, value)
    elif isinstance(value, dict):
        return {k: _resolve_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_resolve_env_vars(item) for item in value]
    return value


def _get_env() -> str:
    """获取当前环境（从环境变量）"""
    return os.getenv("APP_ENV", "development")


def load_toml_config(
    config_dir: str | Path | None = None,
    env: str | None = None,
) -> AppConfig:
    """加载 TOML 配置文件（支持多环境）

    配置加载顺序：
    1. config/app.toml（基础配置）
    2. config/app.{env}.toml（环境特定配置，覆盖基础配置）

    Args:
        config_dir: 配置目录路径，默认为 backend/config/
        env: 环境名称，默认从 APP_ENV 环境变量读取

    Returns:
        AppConfig 配置对象
    """
    config_dir = Path(__file__).parent.parent / "config" if config_dir is None else Path(config_dir)
    env = env or _get_env()

    # 1. 加载基础配置
    base_path = config_dir / "app.toml"
    base_data: dict = {}

    if base_path.exists():
        try:
            with base_path.open("rb") as f:
                base_data = tomllib.load(f)
            logger.info("Loaded base config from %s", base_path)
        except Exception as e:
            logger.error("Failed to load base config: %s", e)

    # 2. 加载环境特定配置（如果存在）
    env_path = config_dir / f"app.{env}.toml"
    if env_path.exists():
        try:
            with env_path.open("rb") as f:
                env_data = tomllib.load(f)
            base_data = _deep_merge(base_data, env_data)
            logger.info("Loaded %s config from %s", env, env_path)
        except Exception as e:
            logger.warning("Failed to load %s config: %s", env, e)

    if not base_data:
        logger.warning("No config files found in %s, using defaults", config_dir)
        return AppConfig()

    # 3. 解析环境变量引用（${VAR} 或 ${VAR:default}）
    resolved_data = _resolve_env_vars(base_data)

    return _dict_to_dataclass(AppConfig, resolved_data)


@lru_cache
def get_app_config() -> AppConfig:
    """获取应用配置单例"""
    return load_toml_config()


# 全局配置实例
app_config = get_app_config()
