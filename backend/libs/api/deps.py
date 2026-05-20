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
from domains.agent.application.chat_model_resolution_use_case import ChatModelResolutionUseCase
from domains.agent.application.checkpoint_service import CheckpointService
from domains.agent.application.listing_studio_prompt_service import (
    ListingStudioPromptTemplateUseCase,
)
from domains.agent.application.listing_studio_use_case import ListingStudioUseCase
from domains.agent.application.memory_service import MemoryService
from domains.agent.application.message_use_case import MessageUseCase
from domains.agent.application.product_image_gen_task_use_case import (
    ProductImageGenTaskUseCase,
)
from domains.agent.application.stats_service import StatsService
from domains.agent.application.video_task_use_case import VideoTaskUseCase
from domains.agent.infrastructure.repositories.agent_repository import AgentRepository
from domains.agent.infrastructure.repositories.message_repository import MessageRepository
from domains.agent.infrastructure.sandbox.lifecycle_adapter import SandboxLifecycleAdapter
from domains.gateway.application.sql_model_catalog import get_model_catalog_adapter
from domains.identity.application import UserUseCase
from domains.identity.application.session_migration_service import (
    AnonymousDataReassignmentService,
)
from domains.session.application import SessionUseCase, TitleUseCase
from libs.db.database import get_db
from libs.iam.deps import get_default_tenant_provisioner
from libs.iam.tenancy import DefaultTenantProvisionerPort

if TYPE_CHECKING:
    from domains.agent.application.listing_studio_image_service import ListingStudioImageService
    from domains.agent.application.storage_config_service import StorageConfigService
    from domains.agent.domain.services.sandbox_lifecycle import SandboxLifecycleService

__all__ = [
    "DbSession",
    "build_session_use_case",
    "get_agent_service",
    "get_anonymous_reassignment_service",
    "get_chat_model_resolution_service",
    "get_chat_service",
    "get_checkpoint_service",
    "get_db",
    "get_listing_studio_image_service",
    "get_listing_studio_prompt_service",
    "get_listing_studio_service",
    "get_login_services",
    "get_mcp_dynamic_prompt_service",
    "get_mcp_dynamic_tool_service",
    "get_mcp_service",
    "get_memory_service",
    "get_product_image_gen_task_service",
    "get_sandbox_service",
    "get_session_service",
    "get_stats_service",
    "get_storage_config_service",
    "get_title_service",
    "get_user_service",
    "get_user_use_case",
    "get_video_task_service",
]


# =============================================================================
# 数据库会话依赖（实现位于 libs.db.database.get_db，此处仅 re-export 与 DbSession）
# =============================================================================

DbSession = Annotated[AsyncSession, Depends(get_db)]


# =============================================================================
# 服务依赖
# =============================================================================


async def get_user_service(
    db: DbSession,
    tenant_provisioner: Annotated[
        DefaultTenantProvisionerPort, Depends(get_default_tenant_provisioner)
    ],
) -> UserUseCase:
    """获取用户服务"""
    return UserUseCase(db, tenant_provisioner=tenant_provisioner)


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


def build_session_use_case(
    db: AsyncSession,
    *,
    sandbox_service: SandboxLifecycleService | None = None,
) -> SessionUseCase:
    """组装 SessionUseCase（注入 Message 应用端口）。"""
    return SessionUseCase(
        db,
        message_service=MessageUseCase(db),
        sandbox_service=sandbox_service,
    )


async def get_session_service(
    db: DbSession,
    request: Request,
) -> SessionUseCase:
    """获取会话服务

    自动注入沙箱生命周期服务（如果可用），实现会话与沙箱生命周期联动。
    """
    sandbox_service = get_sandbox_service(request)
    return build_session_use_case(db, sandbox_service=sandbox_service)


async def get_title_service(db: DbSession) -> TitleUseCase:
    """获取标题服务"""
    return TitleUseCase(db=db)


async def get_chat_service(
    db: DbSession,
    request: Request,
    session_service: SessionUseCase = Depends(get_session_service),
) -> ChatUseCase:
    """获取对话服务"""
    from domains.agent.infrastructure.memory.vector_store_factory import (
        build_memory_indexing_service,
    )

    checkpointer = getattr(request.app.state, "checkpointer", None)
    catalog = get_model_catalog_adapter(db)
    model_resolution = ChatModelResolutionUseCase(db, catalog=catalog)
    return ChatUseCase(
        db,
        session_use_case=session_service,
        session_use_case_factory=build_session_use_case,
        memory_indexing=build_memory_indexing_service(),
        checkpointer=checkpointer,
        model_catalog=catalog,
        model_resolution_use_case=model_resolution,
    )


async def get_checkpoint_service(db: DbSession) -> CheckpointService:
    """获取检查点服务"""
    return CheckpointService(db)


async def get_memory_service(db: DbSession) -> MemoryService:
    """获取记忆服务"""
    return MemoryService(db)


async def get_stats_service(db: DbSession) -> StatsService:
    """获取统计服务"""
    return StatsService(
        identity=UserUseCase(db),
        sessions=build_session_use_case(db),
        agents=AgentRepository(db),
        messages=MessageRepository(db),
    )


async def get_mcp_service(db: DbSession):
    """获取 MCP 管理服务"""
    from domains.agent.application.mcp_use_case import MCPManagementUseCase

    return MCPManagementUseCase(db)


async def get_mcp_dynamic_tool_service(db: DbSession):
    """获取 MCP 动态工具用例"""
    from domains.agent.application.mcp_dynamic_tool_use_case import MCPDynamicToolUseCase

    return MCPDynamicToolUseCase(db)


async def get_mcp_dynamic_prompt_service(db: DbSession):
    """获取 MCP 动态 Prompt 用例"""
    from domains.agent.application.mcp_dynamic_prompt_use_case import MCPDynamicPromptUseCase

    return MCPDynamicPromptUseCase(db)


async def get_video_task_service(
    db: DbSession,
    session_service: SessionUseCase = Depends(get_session_service),
) -> VideoTaskUseCase:
    """获取视频生成任务服务"""
    return VideoTaskUseCase(db, session_use_case=session_service)


async def get_anonymous_reassignment_service(db: DbSession) -> AnonymousDataReassignmentService:
    """匿名数据归并服务（登录/注册后统一入口）。"""
    from libs.identity_bridge_deps import build_anonymous_reassignment_service

    return build_anonymous_reassignment_service(db)


def get_user_use_case(db: DbSession) -> UserUseCase:
    """Identity 写侧 UserUseCase（无 tenant_provisioner；FastAPI 依赖见 ``libs.identity_bridge_deps``）。"""
    from libs.identity_bridge_deps import create_user_use_case

    return create_user_use_case(db)


async def get_login_services(
    db: DbSession,
) -> tuple[UserUseCase, AnonymousDataReassignmentService]:
    """登录编排（UserUseCase + 匿名归并）；FastAPI 依赖见 ``libs.identity_bridge_deps.get_login_services``。"""
    from libs.identity_bridge_deps import build_login_services

    return build_login_services(db)


async def get_listing_studio_service(db: DbSession) -> ListingStudioUseCase:
    """获取 Listing Studio 工作流服务"""
    catalog = get_model_catalog_adapter(db)
    return ListingStudioUseCase(db, catalog=catalog)


async def get_product_image_gen_task_service(db: DbSession) -> ProductImageGenTaskUseCase:
    """获取 8 图生成任务服务（注入 ImageGenerator）"""
    from bootstrap.config import settings  # pylint: disable=import-outside-toplevel
    from domains.agent.infrastructure.llm.image_generator import (
        ImageGenerator,  # pylint: disable=import-outside-toplevel
    )

    image_generator = ImageGenerator(settings)
    return ProductImageGenTaskUseCase(db, image_generator=image_generator)


async def get_listing_studio_prompt_service(db: DbSession) -> ListingStudioPromptTemplateUseCase:
    """获取 Listing Studio 提示词模板服务"""
    return ListingStudioPromptTemplateUseCase(db)


async def get_chat_model_resolution_service(db: DbSession) -> ChatModelResolutionUseCase:
    """获取聊天模型目录解析服务"""
    return ChatModelResolutionUseCase(db, catalog=get_model_catalog_adapter(db))


async def get_storage_config_service(db: DbSession) -> StorageConfigService:
    """获取平台对象存储配置服务"""
    from domains.agent.application.listing_studio_image_factory import (  # pylint: disable=import-outside-toplevel
        create_storage_config_service,
    )

    return create_storage_config_service(db)


async def get_listing_studio_image_service(
    db: DbSession,
) -> ListingStudioImageService:
    """获取 Listing Studio 图片存储服务"""
    from domains.agent.application.listing_studio_image_factory import (  # pylint: disable=import-outside-toplevel
        create_listing_studio_image_service,
    )

    return create_listing_studio_image_service(db)
