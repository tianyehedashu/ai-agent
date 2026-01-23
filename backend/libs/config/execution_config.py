"""
执行环境配置模型

支持分层覆盖：系统默认 → 环境模板 → Agent配置 → 运行时参数
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SandboxMode(str, Enum):
    """沙箱执行模式"""

    DOCKER = "docker"
    LOCAL = "local"
    REMOTE = "remote"


class ResourceConfig(BaseModel):
    """资源限制配置"""

    memory_limit: str = "256m"
    cpu_limit: float = 1.0
    disk_limit: str = "1g"


class NetworkConfig(BaseModel):
    """网络配置"""

    enabled: bool = False
    allowed_hosts: list[str] = Field(default_factory=list)
    dns_servers: list[str] = Field(default_factory=list)


class SecurityConfig(BaseModel):
    """安全配置"""

    read_only_root: bool = True
    no_new_privileges: bool = True
    drop_capabilities: list[str] = Field(default_factory=lambda: ["ALL"])


class SessionPolicyConfig(BaseModel):
    """会话策略配置"""

    # 空闲超时（秒）- 无活动后多久清理
    idle_timeout: int = 7200  # 2 小时（更友好的默认值）

    # 断开超时（秒）- 断开连接后等待重连时间
    disconnect_timeout: int = 1800  # 30 分钟（允许临时离开）

    # 任务完成后保留时间（秒）- 方便用户查看结果
    completion_retain: int = 3600  # 1 小时

    # 最大会话时长（秒）- 硬性限制
    max_session_duration: int = 28800  # 8 小时（支持长时间工作）

    # 每用户最大会话数
    max_sessions_per_user: int = 5

    # 全局最大会话数
    max_total_sessions: int = 200

    # 是否允许会话复用（同一对话复用容器）
    allow_session_reuse: bool = True


class DockerConfig(BaseModel):
    """Docker 特定配置"""

    image: str = "python:3.11-slim"
    packages: list[str] = Field(default_factory=list)
    packages_cmd: str | None = None
    volumes: list[dict[str, Any]] = Field(default_factory=list)

    # 会话模式配置
    session_enabled: bool = True  # 启用会话容器（状态保持）
    workspace_volume: str | None = None  # 主机工作目录，用于持久化
    container_workspace: str = "/workspace"  # 容器内工作目录

    # 会话策略
    session_policy: SessionPolicyConfig = Field(default_factory=SessionPolicyConfig)


class SandboxConfig(BaseModel):
    """沙箱配置"""

    mode: SandboxMode = SandboxMode.DOCKER
    timeout_seconds: int = 30
    resources: ResourceConfig = Field(default_factory=ResourceConfig)
    network: NetworkConfig = Field(default_factory=NetworkConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    docker: DockerConfig = Field(default_factory=DockerConfig)


class ShellConfig(BaseModel):
    """Shell 环境配置"""

    default_shell: str = "/bin/bash"
    work_dir: str = "/workspace"
    env: dict[str, str] = Field(default_factory=dict)


class ToolsConfig(BaseModel):
    """工具配置"""

    enabled: list[str] = Field(default_factory=list)
    disabled: list[str] = Field(default_factory=list)
    require_confirmation: list[str] = Field(default_factory=list)
    auto_approve_patterns: list[str] = Field(default_factory=list)
    config: dict[str, dict[str, Any]] = Field(default_factory=dict)


class MCPServerConfig(BaseModel):
    """MCP 服务器配置"""

    name: str = ""
    description: str = ""
    url: str = ""
    transport: str = "http"  # stdio | http | websocket
    enabled: bool = False
    auto_start: bool = False
    api_key_env: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    headers: dict[str, str] = Field(default_factory=dict)
    tools: dict[str, dict[str, Any]] = Field(default_factory=dict)


class MCPSettingsConfig(BaseModel):
    """MCP 全局设置"""

    connection_timeout: int = 10
    tool_timeout: int = 60
    max_retries: int = 3
    retry_delay_seconds: float = 1.0
    cache_tools: bool = True
    cache_ttl_seconds: int = 300


class MCPConfig(BaseModel):
    """MCP 配置"""

    settings: MCPSettingsConfig = Field(default_factory=MCPSettingsConfig)
    servers: dict[str, MCPServerConfig] = Field(default_factory=dict)


class HITLConfig(BaseModel):
    """Human-in-the-Loop 配置"""

    enabled: bool = True
    require_confirmation: list[str] = Field(default_factory=list)
    auto_approve_patterns: list[str] = Field(default_factory=list)
    confirmation_timeout: int = 300


class LoggingConfig(BaseModel):
    """日志配置"""

    level: str = "info"
    retention_days: int = 7
    log_tool_calls: bool = True
    log_llm_calls: bool = False


class MetadataConfig(BaseModel):
    """元数据配置"""

    version: str = "1.0"
    description: str = ""
    name: str = ""
    tags: list[str] = Field(default_factory=list)
    agent_id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class ExecutionConfig(BaseModel):
    """
    完整执行环境配置

    支持分层合并，优先级从低到高：
    1. 系统默认
    2. 环境模板
    3. Agent 配置
    4. 运行时参数
    """

    # 元数据
    metadata: MetadataConfig = Field(default_factory=MetadataConfig)

    # 继承的模板名称
    extends: str | None = None

    # 核心配置
    sandbox: SandboxConfig = Field(default_factory=SandboxConfig)
    shell: ShellConfig = Field(default_factory=ShellConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    mcp: MCPConfig = Field(default_factory=MCPConfig)
    hitl: HITLConfig = Field(default_factory=HITLConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    def merge_with(self, override: ExecutionConfig) -> ExecutionConfig:
        """
        合并配置，override 优先级更高
        """
        return ConfigMerger.merge(self, override)


class ConfigMerger:
    """配置合并器"""

    @staticmethod
    def merge(base: ExecutionConfig, override: ExecutionConfig) -> ExecutionConfig:
        """
        深度合并两个配置，override 优先

        合并规则：
        - 标量值: override 覆盖 base
        - 列表: override 替换 base（不合并）
        - 字典: 递归合并
        - None 值: 不覆盖
        """
        base_dict = base.model_dump(exclude_none=True)
        override_dict = override.model_dump(exclude_none=True)

        merged = ConfigMerger._deep_merge(base_dict, override_dict)
        return ExecutionConfig.model_validate(merged)

    @staticmethod
    def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        """递归深度合并字典"""
        result = base.copy()

        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = ConfigMerger._deep_merge(result[key], value)
            elif value is not None:
                result[key] = value

        return result
