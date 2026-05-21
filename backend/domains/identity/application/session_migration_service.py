"""
Anonymous Data Reassignment Service - 匿名用户数据归并服务

当匿名用户注册或登录后，将其匿名期间创建的数据迁移到正式用户账号下。
包括：Session、VideoGenTask。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
import uuid

from utils.logging import get_logger

if TYPE_CHECKING:
    from domains.agent.application.ports import VideoTaskApplicationPort
    from domains.session.application.ports import SessionApplicationPort

logger = get_logger(__name__)


@dataclass
class MigrationResult:
    """迁移结果"""

    sessions: int = 0
    video_tasks: int = 0

    @property
    def total(self) -> int:
        return self.sessions + self.video_tasks


class AnonymousDataReassignmentService:
    """匿名数据归并服务

    将匿名用户的 Session 和 VideoGenTask 迁移到正式用户账号。
    仅迁移 user_id IS NULL 的记录，避免重复迁移。
    """

    def __init__(
        self,
        *,
        session_service: SessionApplicationPort,
        video_task_service: VideoTaskApplicationPort,
    ) -> None:
        self.session_service = session_service
        self.video_task_service = video_task_service

    async def migrate(
        self,
        user_id: uuid.UUID | str,
        anonymous_user_id: str,
    ) -> MigrationResult:
        """将匿名用户的数据迁移到正式用户

        Args:
            user_id: 正式用户 ID (UUID 或 UUID 字符串)
            anonymous_user_id: 匿名用户 ID (不含 'anonymous-' 前缀)

        Returns:
            MigrationResult 包含各表迁移数量
        """
        if isinstance(user_id, str):
            user_id = uuid.UUID(user_id)

        session_count = await self.session_service.reassign_anonymous_to_user(
            user_id=user_id,
            anonymous_user_id=anonymous_user_id,
        )
        task_count = await self.video_task_service.reassign_anonymous_to_user(
            user_id=user_id,
            anonymous_user_id=anonymous_user_id,
        )

        result = MigrationResult(sessions=session_count, video_tasks=task_count)

        if result.total > 0:
            logger.info(
                "Migrated anonymous data to user %s: %d sessions, %d video_tasks (anonymous_id=%s)",
                str(user_id)[:8],
                result.sessions,
                result.video_tasks,
                anonymous_user_id[:8],
            )

        return result


async def migrate_anonymous_data_on_auth(
    user_id: uuid.UUID | str,
    anonymous_user_id: str | None,
    *,
    session_service: SessionApplicationPort,
    video_task_service: VideoTaskApplicationPort,
) -> MigrationResult:
    """认证成功后迁移匿名数据的便捷函数

    在登录或注册时调用，将当前浏览器的匿名数据迁移到正式账号。

    Args:
        user_id: 正式用户 ID
        anonymous_user_id: 匿名用户 ID（从 Cookie 获取）

    Returns:
        MigrationResult 迁移结果
    """
    if not anonymous_user_id:
        return MigrationResult()

    service = AnonymousDataReassignmentService(
        session_service=session_service,
        video_task_service=video_task_service,
    )
    return await service.migrate(user_id, anonymous_user_id)
