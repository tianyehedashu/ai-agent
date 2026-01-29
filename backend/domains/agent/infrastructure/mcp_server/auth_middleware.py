"""
MCP Auth Middleware - MCP 认证中间件

验证 API Key 并检查 MCP 作用域权限
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from domains.identity.domain.api_key_types import ApiKeyScope
from utils.logging import get_logger

if TYPE_CHECKING:
    from uuid import UUID

logger = get_logger(__name__)

# 创建 Bearer 认证方案（auto_error=False 以便返回自定义错误）
security = HTTPBearer(auto_error=False)


def get_required_scope_for_server(server_name: str) -> set[ApiKeyScope]:
    """获取服务器所需的作用域

    Args:
        server_name: 服务器名称

    Returns:
        需要的作用域集合
    """
    scope_map = {
        "llm-server": {ApiKeyScope.MCP_LLM_SERVER},
        "filesystem-server": {ApiKeyScope.MCP_FILESYSTEM_SERVER},
        "memory-server": {ApiKeyScope.MCP_MEMORY_SERVER},
        "workflow-server": {ApiKeyScope.MCP_WORKFLOW_SERVER},
        "custom-server": {ApiKeyScope.MCP_CUSTOM_SERVER},
    }
    return scope_map.get(server_name, {ApiKeyScope.MCP_ALL_SERVERS})


async def verify_mcp_access(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> tuple[UUID, UUID, set[ApiKeyScope], str | None]:
    """验证 MCP 访问权限

    Args:
        request: FastAPI 请求对象
        credentials: HTTP Bearer 认证凭据

    Returns:
        (api_key_id, user_id, scopes, client_ip) 元组

    Raises:
        HTTPException: 认证失败
    """
    # 获取客户端 IP
    client_ip = request.client.host if request.client else None

    # 检查 Authorization 头
    if not credentials:
        logger.warning(f"MCP access denied: no credentials provided (IP: {client_ip})")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key required for MCP access. Use Authorization: Bearer sk_...",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 验证 API Key 格式
    api_key = credentials.credentials
    if not api_key.startswith("sk_"):
        logger.warning(f"MCP access denied: invalid key format (IP: {client_ip})")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key format. Must start with 'sk_'",
        )

    # 从路径提取服务器名称
    server_name = request.path_params.get("server_name")
    if not server_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Server name required",
        )

    # 验证 API Key（延迟导入避免循环依赖，verify_mcp_access 在请求时调用）
    from domains.identity.application.api_key_use_case import (
        ApiKeyUseCase,  # pylint: disable=import-outside-toplevel
    )
    from libs.db.database import get_session_context  # pylint: disable=import-outside-toplevel

    async with get_session_context() as db:
        use_case = ApiKeyUseCase(db)
        entity = await use_case.verify_api_key(api_key)

        if not entity:
            logger.warning(
                f"MCP access denied: invalid API key (IP: {client_ip}, "
                f"key_id: {api_key.split('_')[1] if len(api_key.split('_')) > 1 else 'unknown'})"
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired API Key",
            )

        # 检查 API Key 是否有效
        if not entity.is_valid:
            logger.warning(
                f"MCP access denied: API key not valid (IP: {client_ip}, "
                f"key_id: {entity.key_id}, status: {entity.status})"
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"API Key is {entity.status.value}",
            )

        # 检查 MCP 权限
        required_scopes = get_required_scope_for_server(server_name)

        # 拥有 mcp:all 权限可访问所有服务器，否则检查特定服务器权限
        if ApiKeyScope.MCP_ALL_SERVERS not in entity.scopes and not entity.scopes & required_scopes:
            logger.warning(
                "MCP access denied: missing required scope "
                "(IP: %s, key_id: %s, server: %s, required: %s, has: %s)",
                client_ip,
                entity.key_id,
                server_name,
                required_scopes,
                entity.scopes,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required scope: {', '.join(s.value for s in required_scopes)}",
            )

        logger.info(
            f"MCP access granted: server={server_name}, "
            f"key_id={entity.key_id}, user_id={entity.user_id}"
        )

        # 记录 API Key 使用
        try:
            await use_case.record_usage(
                api_key_id=entity.id,
                endpoint=request.url.path,
                method=request.method,
                ip_address=client_ip,
                user_agent=request.headers.get("user-agent"),
                status_code=200,  # 假设成功，实际在响应时更新
                response_time_ms=None,  # SSE 连接无法准确测量响应时间
            )
        except Exception as e:
            # 记录失败不影响请求
            logger.warning(f"Failed to record API Key usage: {e}")

        # 返回结果（需要在上下文管理器内返回，因为 entity 的属性需要数据库会话）
        return entity.id, entity.user_id, entity.scopes, client_ip


async def verify_mcp_access_optional(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> tuple[UUID | None, set[ApiKeyScope], str | None]:
    """可选的 MCP 访问验证

    如果提供了 API Key 则验证，否则返回匿名访问

    Returns:
        (api_key_id, scopes, client_ip) 元组，api_key_id 可能为 None
    """
    client_ip = request.client.host if request.client else None

    if not credentials:
        return None, set(), client_ip

    try:
        api_key_id, _user_id, scopes, _ = await verify_mcp_access(request, credentials)
        return api_key_id, scopes, client_ip
    except HTTPException:
        # 验证失败，返回匿名访问
        return None, set(), client_ip
