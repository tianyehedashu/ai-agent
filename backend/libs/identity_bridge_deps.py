"""Identity 桥接依赖（置于 libs 根，避免 import libs.api 时加载 deps 造成循环）。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from fastapi import Depends

from domains.agent.application.message_use_case import MessageUseCase
from domains.agent.application.video_task_use_case import VideoTaskUseCase
from domains.identity.application.session_migration_service import (
    AnonymousDataReassignmentService,
)
from domains.session.application import SessionUseCase
from libs.db.database import get_db

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def build_session_use_case_for_identity(db: AsyncSession) -> SessionUseCase:
    """组装 SessionUseCase（无沙箱生命周期，供匿名归并等身份流程使用）。"""
    return SessionUseCase(
        db,
        message_service=MessageUseCase(db),
        sandbox_service=None,
    )


async def get_anonymous_reassignment_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AnonymousDataReassignmentService:
    """匿名数据归并服务（登录/注册后统一入口）。"""
    session_service = build_session_use_case_for_identity(db)
    video_task_service = VideoTaskUseCase(db, session_use_case=session_service)
    return AnonymousDataReassignmentService(
        session_service=session_service,
        video_task_service=video_task_service,
    )


__all__ = ["get_anonymous_reassignment_service"]
