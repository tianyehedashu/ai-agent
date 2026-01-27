"""
API Dependencies - 共享 API 依赖注入

提供跨领域共享的 FastAPI 依赖：
- 数据库会话
- 服务工厂

身份认证相关依赖请使用：domains.identity.presentation.deps
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from domains.agent.application import AgentUseCase, ChatUseCase, SessionUseCase, TitleUseCase
from domains.agent.application.checkpoint_service import CheckpointService
from domains.agent.application.mcp_use_case import MCPManagementUseCase
from domains.agent.application.memory_service import MemoryService
from domains.agent.application.stats_service import StatsService
from domains.agent.infrastructure.sandbox.lifecycle_adapter import SandboxLifecycleAdapter
from domains.identity.application import UserUseCase
from libs.db.database import get_session

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from domains.agent.domain.services.sandbox_lifecycle import SandboxLifecycleService

__all__ = [
    "DbSession",
    "get_agent_service",
    "get_chat_service",
    "get_checkpoint_service",
    "get_db",
    "get_mcp_service",
    "get_memory_service",
    "get_sandbox_service",
    "get_session_service",
    "get_stats_service",
    "get_title_service",
    "get_user_service",
]


# =============================================================================
# 数据库会话依赖
# =============================================================================


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话"""
    async for session in get_session():
        yield session


DbSession = Annotated[AsyncSession, Depends(get_db)]


# =============================================================================
# 服务依赖
# =============================================================================


async def get_user_service(db: DbSession) -> UserUseCase:
    """获取用户服务"""
    return UserUseCase(db)


async def get_agent_service(db: DbSession) -> AgentUseCase:
    """获取 Agent 服务"""
    return AgentUseCase(db)


def get_sandbox_service(request: Request) -> SandboxLifecycleService | None:
    """获取沙箱生命周期服务

    从应用状态中获取 SessionManager，并创建 SandboxLifecycleAdapter。
    如果 SessionManager 不可用，返回 None。

    Args:
        request: FastAPI 请求对象

    Returns:
        SandboxLifecycleService 实例，如果不可用则返回 None
    """
    session_manager = getattr(request.app.state, "session_manager", None)
    if session_manager:
        return SandboxLifecycleAdapter(session_manager)
    return None


async def get_session_service(
    db: DbSession,
    request: Request,
) -> SessionUseCase:
    """获取会话服务

    自动注入沙箱生命周期服务（如果可用），实现会话与沙箱生命周期联动。
    """
    sandbox_service = get_sandbox_service(request)
    return SessionUseCase(db, sandbox_service=sandbox_service)


async def get_title_service(db: DbSession) -> TitleUseCase:
    """获取标题服务"""
    return TitleUseCase(db=db)


async def get_chat_service(
    db: DbSession,
    request: Request,
) -> ChatUseCase:
    """获取对话服务"""
    checkpointer = getattr(request.app.state, "checkpointer", None)
    return ChatUseCase(db, checkpointer=checkpointer)


async def get_checkpoint_service(db: DbSession) -> CheckpointService:
    """获取检查点服务"""
    return CheckpointService(db)


async def get_memory_service(db: DbSession) -> MemoryService:
    """获取记忆服务"""
    return MemoryService(db)


async def get_stats_service(db: DbSession) -> StatsService:
    """获取统计服务"""
    return StatsService(db)


async def get_mcp_service(db: DbSession) -> MCPManagementUseCase:
    """获取 MCP 管理服务"""
    return MCPManagementUseCase(db)
