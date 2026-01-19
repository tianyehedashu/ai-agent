"""
Core Configuration Module

提供执行环境配置的加载和管理

架构:
- ExecutionConfigService: 配置服务（协调者）
- ConfigSource: 配置源接口
- ConfigValidator: 配置验证器接口

注意: Protocol 接口定义位于 core.protocols 模块
"""

from .env_resolver import EnvVarResolver
from .execution_config import (
    ConfigMerger,
    DockerConfig,
    ExecutionConfig,
    HITLConfig,
    LoggingConfig,
    MCPConfig,
    MCPServerConfig,
    MCPSettingsConfig,
    MetadataConfig,
    NetworkConfig,
    ResourceConfig,
    SandboxConfig,
    SandboxMode,
    SecurityConfig,
    ShellConfig,
    ToolsConfig,
)
from .service import (
    ExecutionConfigService,
    get_execution_config_service,
    reset_execution_config_service,
)
from .sources import ConfigSource, TomlConfigSource
from .validators import (
    CompositeValidator,
    ConfigValidator,
    SandboxValidator,
    SecurityValidator,
    ToolValidator,
    ValidationResult,
)

__all__ = [
    "CompositeValidator",
    "ConfigMerger",
    "ConfigSource",
    "ConfigValidator",
    "DockerConfig",
    "EnvVarResolver",
    "ExecutionConfig",
    "ExecutionConfigService",
    "HITLConfig",
    "LoggingConfig",
    "MCPConfig",
    "MCPServerConfig",
    "MCPSettingsConfig",
    "MetadataConfig",
    "NetworkConfig",
    "ResourceConfig",
    "SandboxConfig",
    "SandboxMode",
    "SandboxValidator",
    "SecurityConfig",
    "SecurityValidator",
    "ShellConfig",
    "TomlConfigSource",
    "ToolValidator",
    "ToolsConfig",
    "ValidationResult",
    "get_execution_config_service",
    "reset_execution_config_service",
]
