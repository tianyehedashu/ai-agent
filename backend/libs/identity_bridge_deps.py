"""Identity 桥接依赖（置于 libs 根，避免 import libs.api 时加载 deps 造成循环）。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import (
    AsyncSession,  # noqa: TC002 — FastAPI 运行期须解析 Annotated[AsyncSession, Depends]
)

from domains.agent.application.message_use_case import MessageUseCase
from domains.agent.application.video_task_use_case import VideoTaskUseCase
from domains.identity.application.session_migration_service import (
    AnonymousDataReassignmentService,
)
from domains.session.application import SessionUseCase
from libs.db.database import get_db

if TYPE_CHECKING:
    from domains.identity.application import UserUseCase


def build_session_use_case_for_identity(db: AsyncSession) -> SessionUseCase:
    """组装 SessionUseCase（无沙箱生命周期，供匿名归并等身份流程使用）。"""
    return SessionUseCase(
        db,
        message_service=MessageUseCase(db),
        sandbox_service=None,
    )


def build_anonymous_reassignment_service(
    session: AsyncSession,
) -> AnonymousDataReassignmentService:
    """匿名数据归并服务（单 session 装配，供 FastAPI 依赖与子依赖复用）。"""
    session_service = build_session_use_case_for_identity(session)
    video_task_service = VideoTaskUseCase(session, session_use_case=session_service)
    return AnonymousDataReassignmentService(
        session_service=session_service,
        video_task_service=video_task_service,
    )


async def get_anonymous_reassignment_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AnonymousDataReassignmentService:
    """匿名数据归并服务（登录/注册后统一入口）。"""
    return build_anonymous_reassignment_service(session)


def create_user_use_case(session: AsyncSession) -> UserUseCase:
    """Identity 写侧 UserUseCase（延迟 import，避免与 identity.application 循环）。"""
    from domains.identity.application import UserUseCase  # pylint: disable=import-outside-toplevel

    return UserUseCase(session)


def get_user_use_case(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserUseCase:
    """FastAPI 依赖：``create_user_use_case``。"""
    return create_user_use_case(session)


def build_login_services(
    session: AsyncSession,
) -> tuple[UserUseCase, AnonymousDataReassignmentService]:
    """登录编排：UserUseCase + 匿名数据归并（单 session，供 FastAPI / deps 复用）。"""
    return create_user_use_case(session), build_anonymous_reassignment_service(session)


async def get_login_services(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> tuple[UserUseCase, AnonymousDataReassignmentService]:
    """FastAPI 依赖：``build_login_services``。"""
    return build_login_services(session)


__all__ = [
    "build_anonymous_reassignment_service",
    "build_login_services",
    "build_session_use_case_for_identity",
    "create_user_use_case",
    "get_anonymous_reassignment_service",
    "get_login_services",
    "get_user_use_case",
]
