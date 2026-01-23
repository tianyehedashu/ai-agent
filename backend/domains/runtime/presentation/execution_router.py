"""
执行配置 API

提供执行配置的 CRUD 操作
"""

from pathlib import Path
import tomllib
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
import tomli_w

from domains.identity.infrastructure.models.user import User
from shared.infrastructure.config.execution_config import ExecutionConfig
from shared.infrastructure.config.service import (
    ExecutionConfigService,
    get_execution_config_service,
)
from shared.presentation.deps import get_current_user
from domains.runtime.infrastructure.tools.registry import ConfiguredToolRegistry

router = APIRouter(prefix="/execution", tags=["Execution"])


# =============================================================================
# /
# =============================================================================


class TemplateInfo(BaseModel):
    """模板信息"""

    name: str
    description: str
    tags: list[str]


class ConfigValidationResult(BaseModel):
    """配置验证结果"""

    valid: bool
    errors: list[str]
    warnings: list[str]


class ResolvedConfig(BaseModel):
    """解析后的配置"""

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
    """MCP server info."""

    name: str
    description: str
    url: str
    transport: str
    enabled: bool


# =============================================================================
# ?
# =============================================================================


def get_config_service() -> ExecutionConfigService:
    """获取配置服务"""
    return get_execution_config_service()


def _get_agents_dir() -> Path:
    """agents"""
    backend_root = Path(__file__).parent.parent.parent.parent
    return backend_root / "agents"


def _get_config_dir() -> Path:
    """"""
    backend_root = Path(__file__).parent.parent.parent.parent
    return backend_root / "config"


# =============================================================================
# API
# =============================================================================


@router.get("/templates", response_model=list[TemplateInfo])
async def list_templates(
    service: ExecutionConfigService = Depends(get_config_service),
) -> list[TemplateInfo]:
    """



    - python-dev: Python ?
    - node-dev: Node.js ?
    - data-science:
    - minimal:
    """
    templates = service.list_templates()
    return [TemplateInfo(**t) for t in templates]


@router.get("/templates/{template_name}")
async def get_template(
    template_name: str,
    service: ExecutionConfigService = Depends(get_config_service),
) -> dict[str, Any]:
    """


    Args:
        template_name:  python-dev, node-dev?

    Returns:
        ?
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
     Agent

    Args:
        agent_id: Agent ID
        resolve:
            - True:  +  + Agent
            - False: ?Agent ?

    Returns:

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
     Agent

    Args:
        agent_id: Agent ID
        config: ?

    Returns:
        ?
    """
    #
    try:
        validated = ExecutionConfig.model_validate(config)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid config: {e}",
        ) from e

    #
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
     Agent

    ?PUT ATCH ?

    Args:
        agent_id: Agent ID
        config_patch:

    Returns:
        ?
    """
    #
    existing = service.get_agent_config(agent_id)
    if existing:
        #
        patch_config = ExecutionConfig.model_validate(config_patch)
        merged = existing.merge_with(patch_config)
    else:
        merged = ExecutionConfig.model_validate(config_patch)

    #
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
     Agent

    Agent ?

    Args:
        agent_id: Agent ID

    Returns:
        ?
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


    ?

    Args:
        config:

    Returns:
        ?
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




    Args:
        agent_id: Agent ID
        runtime_overrides:

    Returns:
        ?
    """
    sources = ["system_default"]

    #
    agent_config = service.get_agent_config(agent_id)
    if agent_config:
        if agent_config.extends:
            sources.append(f"template:{agent_config.extends}")
        sources.append(f"agent:{agent_id}")

    if runtime_overrides:
        sources.append("runtime_overrides")

    #
    config = service.load_for_agent(agent_id, runtime_overrides)

    return ResolvedConfig(
        config=config.model_dump(),
        sources=sources,
    )


@router.get("/tools")
async def list_tools() -> list[dict[str, Any]]:
    """
    ?

    ?
    - ?
    -
    -
    - ?
    """
    config_dir = _get_config_dir()
    tools_path = config_dir / "tools.toml"

    if not tools_path.exists():
        return []

    with tools_path.open("rb") as f:
        data = tomllib.load(f)

    tools_dict = data.get("tools", {})
    #  name
    tools_list = []
    for name, tool_def in tools_dict.items():
        tool_info = {"name": name, **tool_def}
        tools_list.append(tool_info)

    return tools_list


@router.get("/tools/{tool_name}")
async def get_tool(tool_name: str) -> dict[str, Any]:
    """
    ?

    Args:
        tool_name:

    Returns:
        ?
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
     MCP ?

    ?MCP ?
    -
    - ?
    -
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
            continue  #
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
     Agent

    ?

    Args:
        agent_id: Agent ID

    Returns:

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
     JSON Schema

    ?

    Returns:
        ExecutionConfig ?JSON Schema
    """
    return ExecutionConfigService.get_json_schema()
