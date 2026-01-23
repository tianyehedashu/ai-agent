"""
API Dependencies - 共享 API 依赖注入

提供跨领域共享的 FastAPI 依赖：
- 数据库会话
- 服务工厂

身份认证相关依赖请使用：domains.identity.presentation.deps
"""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from domains.agent.application import AgentUseCase, ChatUseCase, SessionUseCase, TitleUseCase
from domains.agent.application.checkpoint_service import CheckpointService
from domains.agent.application.memory_service import MemoryService
from domains.agent.application.stats_service import StatsService
from domains.identity.application import UserUseCase
from libs.db.database import get_session

__all__ = [
    "DbSession",
    "get_agent_service",
    "get_chat_service",
    "get_checkpoint_service",
    "get_db",
    "get_memory_service",
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


async def get_session_service(db: DbSession) -> SessionUseCase:
    """获取会话服务"""
    return SessionUseCase(db)


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
