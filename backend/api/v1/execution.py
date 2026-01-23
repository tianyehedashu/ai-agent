"""
执行环境配置 API

提供配置的 CRUD 操作和验证
"""

from pathlib import Path
import tomllib
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
import tomli_w

from shared.presentation import get_current_user
from shared.infrastructure.config.execution_config import ExecutionConfig
from shared.infrastructure.config.service import (
    ExecutionConfigService,
    get_execution_config_service,
)
from domains.identity.infrastructure.models.user import User
from domains.runtime.infrastructure.tools.registry import ConfiguredToolRegistry

router = APIRouter(prefix="/execution", tags=["execution"])


# =============================================================================
# 请求/响应模型
# =============================================================================


class TemplateInfo(BaseModel):
    """环境模板信息"""

    name: str
    description: str
    tags: list[str]


class ConfigValidationResult(BaseModel):
    """配置验证结果"""

    valid: bool
    errors: list[str]
    warnings: list[str]


class ResolvedConfig(BaseModel):
    """解析后的配置（用于预览）"""

    config: dict[str, Any]
    sources: list[str]


class ConfigUpdateResponse(BaseModel):
    """配置更新响应"""

    status: str
    agent_id: str


class ToolInfo(BaseModel):
    """工具信息"""

    name: str
    description: str
    category: str
    requires_confirmation: bool
    enabled_by_default: bool


class MCPServerInfo(BaseModel):
    """MCP 服务器信息"""

    name: str
    description: str
    url: str
    transport: str
    enabled: bool


# =============================================================================
# 依赖项
# =============================================================================


def get_config_service() -> ExecutionConfigService:
    """获取配置服务"""
    return get_execution_config_service()


def _get_agents_dir() -> Path:
    """获取 agents 目录路径"""
    backend_root = Path(__file__).parent.parent.parent
    return backend_root / "agents"


def _get_config_dir() -> Path:
    """获取配置目录路径"""
    backend_root = Path(__file__).parent.parent.parent
    return backend_root / "config"


# =============================================================================
# API 端点
# =============================================================================


@router.get("/templates", response_model=list[TemplateInfo])
async def list_templates(
    service: ExecutionConfigService = Depends(get_config_service),
) -> list[TemplateInfo]:
    """
    列出所有可用的环境模板

    返回系统预定义的环境模板列表，包括：
    - python-dev: Python 开发环境
    - node-dev: Node.js 开发环境
    - data-science: 数据科学环境
    - minimal: 最小化环境
    """
    templates = service.list_templates()
    return [TemplateInfo(**t) for t in templates]


@router.get("/templates/{template_name}")
async def get_template(
    template_name: str,
    service: ExecutionConfigService = Depends(get_config_service),
) -> dict[str, Any]:
    """
    获取环境模板详情

    Args:
        template_name: 模板名称（如 python-dev, node-dev）

    Returns:
        模板的完整配置
    """
    template = service.get_template(template_name)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template not found: {template_name}",
        )
    return template.model_dump()


@router.get("/agents/{agent_id}/config")
async def get_agent_config(
    agent_id: str,
    resolve: bool = True,
    current_user: User = Depends(get_current_user),
    service: ExecutionConfigService = Depends(get_config_service),
) -> dict[str, Any]:
    """
    获取 Agent 执行环境配置

    Args:
        agent_id: Agent ID
        resolve: 是否返回合并后的完整配置
            - True: 返回系统默认 + 模板 + Agent 配置合并后的结果
            - False: 仅返回 Agent 级别的配置

    Returns:
        执行环境配置
    """
    if resolve:
        config = service.load_for_agent(agent_id)
    else:
        config = service.get_agent_config(agent_id)
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent config not found: {agent_id}",
            )
    return config.model_dump()


@router.put("/agents/{agent_id}/config")
async def update_agent_config(
    agent_id: str,
    config: dict[str, Any],
    current_user: User = Depends(get_current_user),
) -> ConfigUpdateResponse:
    """
    更新 Agent 执行环境配置

    Args:
        agent_id: Agent ID
        config: 新的配置（会完全覆盖现有配置）

    Returns:
        更新状态
    """
    # 验证配置
    try:
        validated = ExecutionConfig.model_validate(config)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid config: {e}",
        ) from e

    # 保存配置
    config_path = _get_agents_dir() / agent_id / "agent.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)

    with config_path.open("wb") as f:
        tomli_w.dump(validated.model_dump(exclude_none=True), f)

    return ConfigUpdateResponse(status="updated", agent_id=agent_id)


@router.patch("/agents/{agent_id}/config")
async def patch_agent_config(
    agent_id: str,
    config_patch: dict[str, Any],
    current_user: User = Depends(get_current_user),
    service: ExecutionConfigService = Depends(get_config_service),
) -> ConfigUpdateResponse:
    """
    部分更新 Agent 执行环境配置

    与 PUT 不同，PATCH 只更新提供的字段，保留其他字段

    Args:
        agent_id: Agent ID
        config_patch: 要更新的配置片段

    Returns:
        更新状态
    """
    # 加载现有配置
    existing = service.get_agent_config(agent_id)
    if existing:
        # 合并配置
        patch_config = ExecutionConfig.model_validate(config_patch)
        merged = existing.merge_with(patch_config)
    else:
        merged = ExecutionConfig.model_validate(config_patch)

    # 保存配置
    config_path = _get_agents_dir() / agent_id / "agent.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)

    with config_path.open("wb") as f:
        tomli_w.dump(merged.model_dump(exclude_none=True), f)

    return ConfigUpdateResponse(status="updated", agent_id=agent_id)


@router.delete("/agents/{agent_id}/config")
async def delete_agent_config(
    agent_id: str,
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    """
    删除 Agent 执行环境配置

    删除后，Agent 将使用系统默认配置

    Args:
        agent_id: Agent ID

    Returns:
        删除状态
    """
    config_path = _get_agents_dir() / agent_id / "agent.toml"

    if config_path.exists():
        config_path.unlink()
        return {"status": "deleted", "agent_id": agent_id}
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent config not found: {agent_id}",
        )


@router.post("/validate")
async def validate_config(
    config: dict[str, Any],
    current_user: User = Depends(get_current_user),
    service: ExecutionConfigService = Depends(get_config_service),
) -> ConfigValidationResult:
    """
    验证执行环境配置

    检查配置的有效性，返回错误和警告

    Args:
        config: 要验证的配置

    Returns:
        验证结果，包括是否有效、错误列表、警告列表
    """
    try:
        validated = ExecutionConfig.model_validate(config)
        result = service.validate(validated)
    except Exception as e:
        return ConfigValidationResult(
            valid=False,
            errors=[str(e)],
            warnings=[],
        )

    return ConfigValidationResult(
        valid=result.is_valid,
        errors=result.errors,
        warnings=result.warnings,
    )


@router.post("/agents/{agent_id}/preview")
async def preview_resolved_config(
    agent_id: str,
    runtime_overrides: dict[str, Any] | None = None,
    current_user: User = Depends(get_current_user),
    service: ExecutionConfigService = Depends(get_config_service),
) -> ResolvedConfig:
    """
    预览合并后的完整配置

    显示配置来源层级，便于调试和理解配置继承

    Args:
        agent_id: Agent ID
        runtime_overrides: 运行时覆盖参数（可选）

    Returns:
        合并后的配置和来源信息
    """
    sources = ["system_default"]

    # 收集配置来源
    agent_config = service.get_agent_config(agent_id)
    if agent_config:
        if agent_config.extends:
            sources.append(f"template:{agent_config.extends}")
        sources.append(f"agent:{agent_id}")

    if runtime_overrides:
        sources.append("runtime_overrides")

    # 加载合并后的配置
    config = service.load_for_agent(agent_id, runtime_overrides)

    return ResolvedConfig(
        config=config.model_dump(),
        sources=sources,
    )


@router.get("/tools")
async def list_tools() -> dict[str, Any]:
    """
    列出所有可用工具及其定义

    返回系统中所有已定义的工具，包括：
    - 工具名称和描述
    - 参数定义
    - 约束条件
    - 是否需要确认
    """
    config_dir = _get_config_dir()
    tools_path = config_dir / "tools.toml"

    if not tools_path.exists():
        return {}

    with tools_path.open("rb") as f:
        data = tomllib.load(f)

    return data.get("tools", {})


@router.get("/tools/{tool_name}")
async def get_tool(tool_name: str) -> dict[str, Any]:
    """
    获取指定工具的定义

    Args:
        tool_name: 工具名称

    Returns:
        工具的完整定义
    """
    config_dir = _get_config_dir()
    tools_path = config_dir / "tools.toml"

    if not tools_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool not found: {tool_name}",
        )

    with tools_path.open("rb") as f:
        data = tomllib.load(f)

    tools = data.get("tools", {})
    if tool_name not in tools:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool not found: {tool_name}",
        )
    return {tool_name: tools[tool_name]}


@router.get("/mcp/servers")
async def list_mcp_servers() -> list[MCPServerInfo]:
    """
    列出所有配置的 MCP 服务器

    返回系统中配置的所有 MCP 服务器，包括：
    - 服务器名称和描述
    - 连接地址和传输方式
    - 是否启用
    """
    config_dir = _get_config_dir()
    mcp_path = config_dir / "mcp.toml"

    if not mcp_path.exists():
        return []

    with mcp_path.open("rb") as f:
        mcp_config = tomllib.load(f)

    servers = mcp_config.get("servers", {})

    result = []
    for name, config in servers.items():
        if name.startswith("_"):
            continue  # 跳过模板
        result.append(
            MCPServerInfo(
                name=name,
                description=config.get("description", ""),
                url=config.get("url", ""),
                transport=config.get("transport", "http"),
                enabled=config.get("enabled", False),
            )
        )

    return result


@router.get("/agents/{agent_id}/effective-tools")
async def get_effective_tools(
    agent_id: str,
    current_user: User = Depends(get_current_user),
    service: ExecutionConfigService = Depends(get_config_service),
) -> dict[str, Any]:
    """
    获取 Agent 最终生效的工具列表

    返回合并配置后实际启用的工具，以及每个工具是否需要确认

    Args:
        agent_id: Agent ID

    Returns:
        生效的工具列表和确认要求
    """
    config = service.load_for_agent(agent_id)
    registry = ConfiguredToolRegistry(config)

    tools_info = []
    for tool in registry.list_all():
        tools_info.append(
            {
                "name": tool.name,
                "requires_confirmation": registry.requires_confirmation(tool.name),
            }
        )

    return {
        "agent_id": agent_id,
        "tools": tools_info,
        "total": len(tools_info),
    }


@router.get("/schema")
async def get_config_schema() -> dict[str, Any]:
    """
    获取配置 JSON Schema

    用于前端动态生成配置表单

    Returns:
        ExecutionConfig 的 JSON Schema
    """
    return ExecutionConfigService.get_json_schema()
