"""
执行环境配置服务

协调配置源、验证器，实现分层加载逻辑
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from utils.logging import get_logger

from .env_resolver import EnvVarResolver
from .execution_config import ConfigMerger, ExecutionConfig
from .sources.toml_source import AgentTomlSource, TomlConfigSource
from .validators.composite import CompositeValidator

if TYPE_CHECKING:
    from .sources.base import ConfigSource
    from .validators.base import ConfigValidator, ValidationResult

logger = get_logger(__name__)


class ExecutionConfigService:
    """
    执行环境配置服务

    职责：
    - 协调配置源、验证器
    - 实现分层加载逻辑
    - 管理缓存

    不包含：
    - 具体的文件解析（委托给 ConfigSource）
    - 验证逻辑（委托给 ConfigValidator）
    - 工具确认检查（保留在 ConfiguredToolRegistry）
    """

    def __init__(
        self,
        system_source: ConfigSource,
        template_source: ConfigSource,
        agent_source: ConfigSource,
        validator: ConfigValidator | None = None,
        env_resolver: EnvVarResolver | None = None,
    ) -> None:
        """
        初始化配置服务

        Args:
            system_source: 系统默认配置源
            template_source: 环境模板配置源
            agent_source: Agent 配置源
            validator: 配置验证器
            env_resolver: 环境变量解析器
        """
        self.system_source = system_source
        self.template_source = template_source
        self.agent_source = agent_source
        self.validator = validator or CompositeValidator.default()
        self.env_resolver = env_resolver or EnvVarResolver()

        # 缓存
        self._system_default: ExecutionConfig | None = None
        self._templates: dict[str, ExecutionConfig] = {}

    def load_for_agent(
        self,
        agent_id: str,
        runtime_overrides: dict[str, Any] | None = None,
        *,
        validate: bool = False,
    ) -> ExecutionConfig:
        """
        为指定 Agent 加载完整配置

        Args:
            agent_id: Agent ID
            runtime_overrides: 运行时覆盖参数
            validate: 是否验证配置

        Returns:
            合并后的完整配置

        Raises:
            ValueError: 当 validate=True 且配置有错误时
        """
        # 1. 加载系统默认
        config = self._load_system_default()
        logger.debug("Loaded system default config")

        # 2. 加载 Agent 原始配置（字典形式，只包含显式设置的值）
        agent_raw = self._load_agent_raw(agent_id)

        if agent_raw:
            # 3. 如果 Agent 指定了模板，先合并模板
            extends = agent_raw.get("extends")
            if extends:
                template = self._load_template(extends)
                if template:
                    config = ConfigMerger.merge(config, template)
                    logger.debug("Merged template: %s", extends)

            # 4. 合并 Agent 特定配置（使用原始字典，避免默认值覆盖）
            # 移除 extends 字段，因为它不是配置本身
            agent_overrides = {k: v for k, v in agent_raw.items() if k != "extends"}
            if agent_overrides:
                resolved = self.env_resolver.resolve(agent_overrides)
                agent_config = ExecutionConfig.model_validate(resolved)
                config = ConfigMerger.merge(config, agent_config)
                logger.debug("Merged agent config: %s", agent_id)

        # 5. 合并运行时参数
        if runtime_overrides:
            resolved = self.env_resolver.resolve(runtime_overrides)
            runtime_config = ExecutionConfig.model_validate(resolved)
            config = ConfigMerger.merge(config, runtime_config)
            logger.debug("Merged runtime overrides")

        # 6. 可选验证
        if validate:
            result = self.validator.validate(config)
            for warning in result.warnings:
                logger.warning("Config warning: %s", warning)
            if not result.is_valid:
                raise ValueError(f"Invalid configuration: {'; '.join(result.errors)}")

        return config

    def _load_system_default(self) -> ExecutionConfig:
        """加载系统默认配置"""
        if self._system_default is None:
            self._system_default = self._load_and_resolve("execution", self.system_source)
            if self._system_default is None:
                logger.warning("System default config not found, using defaults")
                self._system_default = ExecutionConfig()
        return self._system_default

    def _load_template(self, template_name: str) -> ExecutionConfig | None:
        """加载环境模板（支持递归继承）"""
        if template_name in self._templates:
            return self._templates[template_name]

        template = self._load_and_resolve(template_name, self.template_source)
        if template is None:
            logger.warning("Template not found: %s", template_name)
            return None

        # 递归加载父模板
        if template.extends:
            parent = self._load_template(template.extends)
            if parent:
                template = ConfigMerger.merge(parent, template)

        self._templates[template_name] = template
        return template

    def get_template(self, template_name: str) -> ExecutionConfig | None:
        """
        获取环境模板

        Args:
            template_name: 模板名称

        Returns:
            模板配置，如果不存在则返回 None
        """
        return self._load_template(template_name)

    def get_agent_config(self, agent_id: str) -> ExecutionConfig | None:
        """
        获取 Agent 配置（仅 Agent 级别，不合并）

        Args:
            agent_id: Agent ID

        Returns:
            Agent 配置，如果不存在则返回 None
        """
        return self._load_and_resolve(agent_id, self.agent_source)

    def _load_agent_raw(self, agent_id: str) -> dict[str, Any] | None:
        """
        加载 Agent 原始配置（字典形式）

        返回原始字典而不是 ExecutionConfig，避免默认值填充
        """
        data = self.agent_source.load(agent_id)
        if data is None:
            return None
        return self.env_resolver.resolve(data)

    def _load_and_resolve(
        self,
        identifier: str,
        source: ConfigSource,
    ) -> ExecutionConfig | None:
        """加载并解析配置"""
        data = source.load(identifier)
        if data is None:
            return None

        resolved = self.env_resolver.resolve(data)
        return ExecutionConfig.model_validate(resolved)

    def validate(self, config: ExecutionConfig) -> ValidationResult:
        """验证配置"""
        return self.validator.validate(config)

    def list_templates(self) -> list[dict[str, Any]]:
        """列出所有可用的环境模板"""
        templates = []

        for name in self.template_source.list_available():
            try:
                config = self._load_template(name)
                if config:
                    templates.append(
                        {
                            "name": name,
                            "description": config.metadata.description,
                            "tags": config.metadata.tags,
                        }
                    )
            except Exception as e:
                logger.error("Failed to load template %s: %s", name, e)

        return templates

    def clear_cache(self) -> None:
        """清理缓存"""
        self._system_default = None
        self._templates.clear()
        logger.info("Configuration cache cleared")

    @staticmethod
    def get_json_schema() -> dict[str, Any]:
        """获取配置的 JSON Schema"""
        return ExecutionConfig.model_json_schema()


# 单例实例
_service_instance: ExecutionConfigService | None = None


def get_execution_config_service(
    config_dir: Path | str | None = None,
    agents_dir: Path | str | None = None,
) -> ExecutionConfigService:
    """
    获取配置服务单例

    Args:
        config_dir: 配置目录（仅首次调用有效）
        agents_dir: agents 目录（仅首次调用有效）

    Returns:
        配置服务实例
    """
    global _service_instance

    if _service_instance is None:
        # 默认路径
        backend_root = Path(__file__).parent.parent.parent
        config_path = Path(config_dir) if config_dir else backend_root / "config"
        agents_path = Path(agents_dir) if agents_dir else backend_root / "agents"

        _service_instance = ExecutionConfigService(
            system_source=TomlConfigSource(config_path),
            template_source=TomlConfigSource(config_path / "environments"),
            agent_source=AgentTomlSource(agents_path),
        )

    return _service_instance


def reset_execution_config_service() -> None:
    """重置配置服务单例（主要用于测试）"""
    global _service_instance
    _service_instance = None
