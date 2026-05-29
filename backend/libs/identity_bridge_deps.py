"""Identity 桥接依赖（置于 libs 根，避免 import libs.api 时加载 deps 造成循环）。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import (
    AsyncSession,  # noqa: TC002 — FastAPI 运行期须解析 Annotated[AsyncSession, Depends]
)

from domains.agent.application.message_use_case import MessageUseCase
from domains.session.application import SessionUseCase
from libs.db.database import get_db

if TYPE_CHECKING:
    from domains.identity.application import UserUseCase


def build_session_use_case_for_identity(db: AsyncSession) -> SessionUseCase:
    """组装 SessionUseCase（无沙箱生命周期，供身份流程使用）。"""
    return SessionUseCase(
        db,
        message_service=MessageUseCase(db),
        sandbox_service=None,
    )


def create_user_use_case(session: AsyncSession) -> UserUseCase:
    """Identity 写侧 UserUseCase（延迟 import，避免与 identity.application 循环）。"""
    from domains.identity.application import UserUseCase  # pylint: disable=import-outside-toplevel

    return UserUseCase(session)


def get_user_use_case(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserUseCase:
    """FastAPI 依赖：``create_user_use_case``。"""
    return create_user_use_case(session)


__all__ = [
    "build_session_use_case_for_identity",
    "create_user_use_case",
    "get_user_use_case",
]
