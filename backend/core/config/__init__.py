"""
Core Configuration Module

提供执行环境配置的加载和管理

架构:
- ExecutionConfigService: 配置服务（协调者）
- ConfigSource: 配置源接口
- ConfigValidator: 配置验证器接口
"""

import importlib.util
from pathlib import Path

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

# 导入 core.config.py 模块中的 Protocol 类
# 因为 core.config 现在是包，需要使用 importlib 导入模块文件
_core_config_module_path = Path(__file__).parent.parent / "config.py"
if _core_config_module_path.exists():
    _spec = importlib.util.spec_from_file_location("core_config_module", _core_config_module_path)
    if _spec and _spec.loader:
        _core_config_module = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_core_config_module)
        # 导出 Protocol 类
        AuthConfig = _core_config_module.AuthConfig
        ImageGeneratorConfig = _core_config_module.ImageGeneratorConfig
        LLMConfig = _core_config_module.LLMConfig
        MemoryConfig = _core_config_module.MemoryConfig
        QualityConfig = _core_config_module.QualityConfig
        SandboxConfigProtocol = _core_config_module.SandboxConfig
    else:
        # 如果无法加载，提供占位符以避免导入错误
        from typing import Protocol

        class AuthConfig(Protocol):  # type: ignore[no-redef]
            pass

        class ImageGeneratorConfig(Protocol):  # type: ignore[no-redef]
            pass

        class LLMConfig(Protocol):  # type: ignore[no-redef]
            pass

        class MemoryConfig(Protocol):  # type: ignore[no-redef]
            pass

        class QualityConfig(Protocol):  # type: ignore[no-redef]
            pass

        class SandboxConfigProtocol(Protocol):  # type: ignore[no-redef]
            pass
else:
    # 如果文件不存在，提供占位符
    from typing import Protocol

    class AuthConfig(Protocol):  # type: ignore[no-redef]
        pass

    class ImageGeneratorConfig(Protocol):  # type: ignore[no-redef]
        pass

    class LLMConfig(Protocol):  # type: ignore[no-redef]
        pass

    class MemoryConfig(Protocol):  # type: ignore[no-redef]
        pass

    class QualityConfig(Protocol):  # type: ignore[no-redef]
        pass

    class SandboxConfigProtocol(Protocol):  # type: ignore[no-redef]
        pass


__all__ = [
    "AuthConfig",
    "CompositeValidator",
    "ConfigMerger",
    "ConfigSource",
    "ConfigValidator",
    "DockerConfig",
    "EnvVarResolver",
    "ExecutionConfig",
    "ExecutionConfigService",
    "HITLConfig",
    "ImageGeneratorConfig",
    "LLMConfig",
    "LoggingConfig",
    "MCPConfig",
    "MCPServerConfig",
    "MCPSettingsConfig",
    "MemoryConfig",
    "MetadataConfig",
    "NetworkConfig",
    "QualityConfig",
    "ResourceConfig",
    "SandboxConfig",
    "SandboxConfigProtocol",
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
