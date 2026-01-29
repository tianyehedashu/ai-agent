"""
MCP Server Scopes - MCP 服务器作用域

定义不同的 MCP 服务器类型及其对应的工具集
"""

from enum import Enum


class MCPServerScope(str, Enum):
    """MCP 服务器作用域

    每个 MCP 服务器封装不同的工具集
    """
    LLM = "llm-server"                    # LLM 调用服务器
    FILESYSTEM = "filesystem-server"      # 文件系统服务器
    MEMORY = "memory-server"              # 记忆系统服务器
    WORKFLOW = "workflow-server"          # 工作流服务器
    CUSTOM = "custom-server"              # 自定义服务器

    @classmethod
    def from_name(cls, name: str) -> "MCPServerScope":
        """从名称获取作用域

        Args:
            name: 服务器名称（如 "llm-server"）

        Returns:
            MCPServerScope 枚举值

        Raises:
            ValueError: 无效的服务器名称
        """
        for scope in cls:
            if scope.value == name:
                return scope
        raise ValueError(f"Unknown MCP server: {name}")

    @classmethod
    def get_display_name(cls, scope: "MCPServerScope") -> str:
        """获取显示名称"""
        names = {
            cls.LLM: "LLM Server",
            cls.FILESYSTEM: "Filesystem Server",
            cls.MEMORY: "Memory Server",
            cls.WORKFLOW: "Workflow Server",
            cls.CUSTOM: "Custom Server",
        }
        return names.get(scope, scope.value)

    @classmethod
    def get_description(cls, scope: "MCPServerScope") -> str:
        """获取服务器描述"""
        descriptions = {
            cls.LLM: "大语言模型调用服务，支持多种 LLM 提供商",
            cls.FILESYSTEM: "文件系统操作服务，支持文件读写、搜索等",
            cls.MEMORY: "记忆系统服务，支持短期和长期记忆存储",
            cls.WORKFLOW: "工作流执行服务，支持 Agent 工作流编排",
            cls.CUSTOM: "自定义工具服务，支持用户定义的工具集",
        }
        return descriptions.get(scope, "Unknown server")
