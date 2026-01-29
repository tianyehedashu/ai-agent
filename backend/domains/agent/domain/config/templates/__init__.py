"""
MCP 服务器模板系统

提供预配置的 MCP 服务器模板及有效配置合并逻辑。
"""

from typing import Any

from domains.agent.domain.config.mcp_config import (
    MCPEnvironmentType,
    MCPScope,
    MCPServerEntityConfig,
    MCPTemplate,
)

# 内置模板列表
BUILTIN_TEMPLATES: list[MCPTemplate] = [
    # 1. Filesystem MCP
    MCPTemplate(
        id="filesystem",
        name="filesystem",
        display_name="文件系统",
        description="读写本地文件系统（在沙箱中运行）",
        category="development",
        icon="file",
        default_config=MCPServerEntityConfig(
            name="filesystem",
            display_name="文件系统",
            url="stdio://filesystem",
            scope=MCPScope.SYSTEM,
            env_type=MCPEnvironmentType.PREINSTALLED,
            env_config={"allowed_roots": ["/workspace"]},
            enabled=True,
        ),
        required_fields=[],
        optional_fields=["allowed_roots"],
        field_labels={"allowed_roots": "允许访问的目录"},
        field_placeholders={"allowed_roots": "/workspace"},
        field_help_texts={"allowed_roots": "指定沙箱中允许访问的目录路径，多个路径用逗号分隔"},
    ),
    # 2. GitHub MCP
    MCPTemplate(
        id="github",
        name="github",
        display_name="GitHub",
        description="GitHub 仓库管理和操作",
        category="development",
        icon="github",
        default_config=MCPServerEntityConfig(
            name="github",
            display_name="GitHub",
            url="stdio://github",
            scope=MCPScope.USER,
            env_type=MCPEnvironmentType.DYNAMIC_INJECTED,
            env_config={"github_token": ""},
            enabled=True,
        ),
        required_fields=["github_token"],
        optional_fields=[],
        field_labels={"github_token": "GitHub Token"},
        field_placeholders={"github_token": "ghp_xxxxxxxxxxxx"},
        field_help_texts={"github_token": "GitHub Personal Access Token，需要 repo 权限"},
    ),
    # 3. Postgres MCP
    MCPTemplate(
        id="postgres",
        name="postgres",
        display_name="PostgreSQL",
        description="PostgreSQL 数据库操作",
        category="database",
        icon="database",
        default_config=MCPServerEntityConfig(
            name="postgres",
            display_name="PostgreSQL",
            url="stdio://postgres",
            scope=MCPScope.USER,
            env_type=MCPEnvironmentType.DYNAMIC_INJECTED,
            env_config={
                "connection_string": "",
            },
            enabled=True,
        ),
        required_fields=["connection_string"],
        optional_fields=[],
        field_labels={"connection_string": "数据库连接字符串"},
        field_placeholders={
            "connection_string": "postgresql://user:password@localhost:5432/dbname"
        },
        field_help_texts={
            "connection_string": "PostgreSQL 连接字符串，包含数据库地址、用户名、密码等"
        },
    ),
    # 4. Slack MCP
    MCPTemplate(
        id="slack",
        name="slack",
        display_name="Slack",
        description="Slack 消息和频道管理",
        category="communication",
        icon="slack",
        default_config=MCPServerEntityConfig(
            name="slack",
            display_name="Slack",
            url="stdio://slack",
            scope=MCPScope.USER,
            env_type=MCPEnvironmentType.DYNAMIC_INJECTED,
            env_config={"slack_bot_token": ""},
            enabled=True,
        ),
        required_fields=["slack_bot_token"],
        optional_fields=[],
        field_labels={"slack_bot_token": "Slack Bot Token"},
        field_placeholders={"slack_bot_token": "xoxb-xxxxxxxxxxxx-xxxxxxxxxxxx"},
        field_help_texts={"slack_bot_token": "Slack Bot Token，从 Slack App 配置中获取"},
    ),
    # 5. Brave Search MCP
    MCPTemplate(
        id="brave-search",
        name="brave_search",
        display_name="Brave 搜索",
        description="Brave 搜索引擎集成",
        category="search",
        icon="search",
        default_config=MCPServerEntityConfig(
            name="brave_search",
            display_name="Brave 搜索",
            url="stdio://brave-search",
            scope=MCPScope.USER,
            env_type=MCPEnvironmentType.DYNAMIC_INJECTED,
            env_config={"api_key": ""},
            enabled=True,
        ),
        required_fields=["api_key"],
        optional_fields=[],
        field_labels={"api_key": "API Key"},
        field_placeholders={"api_key": "BSxxxxxxxxxxxxx"},
        field_help_texts={
            "api_key": "Brave Search API Key，从 https://api.search.brave.com/app/keys 获取"
        },
    ),
]


def get_effective_env_config(
    env_config: dict[str, Any],
    template_id: str | None,
    inherit_defaults: bool,
) -> dict[str, Any]:
    """
    获取实例的有效 env_config（考虑模板继承）。

    当 inherit_defaults 为 True 且 template_id 存在时，
    将模板默认 env_config 与实例 env_config 合并，实例值优先。

    Args:
        env_config: 实例当前 env_config
        template_id: 来源模板 ID
        inherit_defaults: 是否继承模板默认配置

    Returns:
        合并后的 env_config
    """
    if not inherit_defaults or not template_id:
        return env_config
    template = next((t for t in BUILTIN_TEMPLATES if t.id == template_id), None)
    if not template:
        return env_config
    return {**template.default_config.env_config, **env_config}
