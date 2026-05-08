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

from domains.agent.application import AgentUseCase, ChatUseCase
from domains.agent.application.checkpoint_service import CheckpointService
from domains.agent.application.mcp_dynamic_prompt_use_case import MCPDynamicPromptUseCase
from domains.agent.application.mcp_dynamic_tool_use_case import MCPDynamicToolUseCase
from domains.agent.application.mcp_use_case import MCPManagementUseCase
from domains.agent.application.memory_service import MemoryService
from domains.agent.application.product_image_gen_task_use_case import (
    ProductImageGenTaskUseCase,
)
from domains.agent.application.product_info_prompt_service import (
    ProductInfoPromptTemplateUseCase,
)
from domains.agent.application.product_info_use_case import ProductInfoUseCase
from domains.agent.application.user_model_use_case import UserModelUseCase
from domains.agent.application.stats_service import StatsService
from domains.agent.application.video_task_use_case import VideoTaskUseCase
from domains.agent.infrastructure.sandbox.lifecycle_adapter import SandboxLifecycleAdapter
from domains.identity.application import UserUseCase
from domains.session.application import SessionUseCase, TitleUseCase
from libs.db.database import get_db

if TYPE_CHECKING:
    from domains.agent.domain.services.sandbox_lifecycle import SandboxLifecycleService

__all__ = [
    "DbSession",
    "get_agent_service",
    "get_chat_service",
    "get_checkpoint_service",
    "get_db",
    "get_mcp_dynamic_prompt_service",
    "get_mcp_dynamic_tool_service",
    "get_mcp_service",
    "get_memory_service",
    "get_product_image_gen_task_service",
    "get_product_info_prompt_service",
    "get_product_info_service",
    "get_sandbox_service",
    "get_session_service",
    "get_stats_service",
    "get_title_service",
    "get_user_model_service",
    "get_user_service",
    "get_video_task_service",
]


# =============================================================================
# 数据库会话依赖（实现位于 libs.db.database.get_db，此处仅 re-export 与 DbSession）
# =============================================================================

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

    从应用状态中获取 SandboxManager，并创建 SandboxLifecycleAdapter。
    如果 SandboxManager 不可用，返回 None。

    Args:
        request: FastAPI 请求对象

    Returns:
        SandboxLifecycleService 实例，如果不可用则返回 None
    """
    sandbox_manager = getattr(request.app.state, "sandbox_manager", None)
    if sandbox_manager:
        return SandboxLifecycleAdapter(sandbox_manager)
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
    session_service: SessionUseCase = Depends(get_session_service),
) -> ChatUseCase:
    """获取对话服务"""
    checkpointer = getattr(request.app.state, "checkpointer", None)
    return ChatUseCase(
        db,
        session_use_case=session_service,
        session_use_case_factory=SessionUseCase,
        checkpointer=checkpointer,
    )


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


async def get_mcp_dynamic_tool_service(db: DbSession) -> MCPDynamicToolUseCase:
    """获取 MCP 动态工具用例"""
    return MCPDynamicToolUseCase(db)


async def get_mcp_dynamic_prompt_service(db: DbSession) -> MCPDynamicPromptUseCase:
    """获取 MCP 动态 Prompt 用例"""
    return MCPDynamicPromptUseCase(db)


async def get_video_task_service(
    db: DbSession,
    session_service: SessionUseCase = Depends(get_session_service),
) -> VideoTaskUseCase:
    """获取视频生成任务服务"""
    return VideoTaskUseCase(db, session_use_case=session_service)


async def get_product_info_service(db: DbSession) -> ProductInfoUseCase:
    """获取产品信息工作流服务"""
    return ProductInfoUseCase(db)


async def get_product_image_gen_task_service(db: DbSession) -> ProductImageGenTaskUseCase:
    """获取 8 图生成任务服务（注入 ImageGenerator）"""
    from bootstrap.config import settings  # pylint: disable=import-outside-toplevel
    from domains.agent.infrastructure.llm.image_generator import ImageGenerator  # pylint: disable=import-outside-toplevel

    image_generator = ImageGenerator(settings)
    return ProductImageGenTaskUseCase(db, image_generator=image_generator)


async def get_product_info_prompt_service(db: DbSession) -> ProductInfoPromptTemplateUseCase:
    """获取产品信息提示词模板服务"""
    return ProductInfoPromptTemplateUseCase(db)


async def get_user_model_service(db: DbSession) -> UserModelUseCase:
    """获取用户模型管理服务"""
    return UserModelUseCase(db)
